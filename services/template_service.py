"""Eşleştirme kuralı şablonlarını kullanıcı profilinde saklar."""

from __future__ import annotations

import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from services.matching_service import (
    DuplicateMode,
    LogicMode,
    MatchOperator,
    MatchRule,
    MultiMatchConfig,
)
from utils.value_normalizers import NormalizationOptions, ValueKind
from utils.runtime_paths import user_data_directory


class TemplateService:
    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            path = user_data_directory() / "matching_templates.json"
        self.path = Path(path)

    def list_names(self) -> list[str]:
        return sorted(self._load().keys(), key=str.casefold)

    def get(self, name: str) -> MultiMatchConfig:
        data = self._load()
        if name not in data:
            raise KeyError(f"Şablon bulunamadı: {name}")
        return self._decode(data[name])

    def save(self, name: str, config: MultiMatchConfig) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Şablon adı boş olamaz.")
        data = self._load()
        data[name] = self._encode(config)
        self._write(data)

    def delete(self, name: str) -> None:
        data = self._load()
        if name in data:
            del data[name]
            self._write(data)

    def _load(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        try:
            content = json.loads(self.path.read_text(encoding="utf-8"))
            return content if isinstance(content, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def _encode(config: MultiMatchConfig) -> dict[str, object]:
        return {
            "logic": config.logic.value,
            "duplicate_mode": config.duplicate_mode.value,
            "rules": [
                {
                    "left_column": rule.left_column,
                    "right_column": rule.right_column,
                    "operator": rule.operator.value,
                    "primary": rule.primary,
                    "normalization": {
                        **asdict(rule.normalization),
                        "kind": rule.normalization.kind.value,
                        "tolerance": str(rule.normalization.tolerance),
                    },
                }
                for rule in config.rules
            ],
        }

    @staticmethod
    def _decode(data: dict[str, object]) -> MultiMatchConfig:
        rules = []
        for item in data.get("rules", []):
            normalization = item.get("normalization", {})
            options = NormalizationOptions(
                kind=ValueKind(normalization.get("kind", ValueKind.AUTO.value)),
                trim=bool(normalization.get("trim", True)),
                case_insensitive=bool(normalization.get("case_insensitive", True)),
                remove_internal_spaces=bool(normalization.get("remove_internal_spaces", False)),
                empty_matches_empty=bool(normalization.get("empty_matches_empty", False)),
                tolerance=Decimal(str(normalization.get("tolerance", "0"))),
                date_tolerance_seconds=int(normalization.get("date_tolerance_seconds", 0)),
            )
            rules.append(
                MatchRule(
                    str(item["left_column"]),
                    str(item["right_column"]),
                    MatchOperator(item.get("operator", MatchOperator.EQUALS.value)),
                    options,
                    bool(item.get("primary", False)),
                )
            )
        return MultiMatchConfig(
            tuple(rules),
            LogicMode(data.get("logic", LogicMode.AND.value)),
            DuplicateMode(data.get("duplicate_mode", DuplicateMode.ONE_TO_ONE.value)),
        )
