"""Tek ve çok sütunlu, deterministik veri eşleştirme motoru."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from utils.plate_utils import normalize_plate_series
from utils.value_normalizers import NormalizationOptions, ValueKind, normalize_series


class OutputMode(str, Enum):
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    ALL = "all"


class LogicMode(str, Enum):
    AND = "and"
    OR = "or"


class DuplicateMode(str, Enum):
    ONE_TO_ONE = "one_to_one"
    ALL_MATCHES = "all_matches"
    UNIQUE_ONLY = "unique_only"


class MatchOperator(str, Enum):
    EQUALS = "equals"
    NUMERIC_TOLERANCE = "numeric_tolerance"
    DATE_TOLERANCE = "date_tolerance"


@dataclass(slots=True, frozen=True)
class MatchRule:
    left_column: str
    right_column: str
    operator: MatchOperator = MatchOperator.EQUALS
    normalization: NormalizationOptions = NormalizationOptions()
    primary: bool = False

    def label(self) -> str:
        return f"{self.left_column} = {self.right_column}"


@dataclass(slots=True, frozen=True)
class MultiMatchConfig:
    rules: tuple[MatchRule, ...]
    logic: LogicMode = LogicMode.AND
    duplicate_mode: DuplicateMode = DuplicateMode.ONE_TO_ONE
    max_all_match_pairs: int = 1_000_000

    def __post_init__(self) -> None:
        if not self.rules:
            raise ValueError("En az bir eşleştirme kuralı ekleyin.")


@dataclass(slots=True, frozen=True)
class MatchSummary:
    total_records: int
    reference_plate_count: int
    matched_records: int
    unmatched_records: int
    matched_unique_plates: int
    unmatched_unique_plates: int

    def as_rows(self) -> list[tuple[str, int]]:
        return [
            ("Toplam kayıt sayısı", self.total_records),
            ("Eşleşen kayıt sayısı", self.matched_records),
            ("Eşleşmeyen kayıt sayısı", self.unmatched_records),
            ("Referans plaka sayısı", self.reference_plate_count),
            ("Eşleşen benzersiz plaka sayısı", self.matched_unique_plates),
            ("Eşleşmeyen benzersiz plaka sayısı", self.unmatched_unique_plates),
        ]


@dataclass(slots=True)
class MatchResult:
    parking_data: pd.DataFrame
    match_mask: np.ndarray
    summary: MatchSummary
    parking_plate_column: str

    def indices_for_mode(self, mode: OutputMode) -> np.ndarray:
        if mode is OutputMode.MATCHED:
            return np.flatnonzero(self.match_mask)
        if mode is OutputMode.UNMATCHED:
            return np.flatnonzero(~self.match_mask)
        return np.arange(len(self.parking_data), dtype=np.int64)


@dataclass(slots=True, frozen=True)
class MultiMatchSummary:
    left_total: int
    right_total: int
    matched_pairs: int
    left_unmatched: int
    right_unmatched: int
    partial_candidates: int

    def as_rows(self) -> list[tuple[str, int]]:
        return [
            ("Dosya 1 toplam kayıt", self.left_total),
            ("Dosya 2 toplam kayıt", self.right_total),
            ("Eşleşen kayıt çifti", self.matched_pairs),
            ("Dosya 1 eşleşmeyen", self.left_unmatched),
            ("Dosya 2 eşleşmeyen", self.right_unmatched),
            ("Kısmi eşleşme adayı", self.partial_candidates),
        ]


@dataclass(slots=True)
class MultiMatchResult:
    left_data: pd.DataFrame
    right_data: pd.DataFrame
    matched_pairs: pd.DataFrame
    left_unmatched: pd.DataFrame
    right_unmatched: pd.DataFrame
    partial_matches: pd.DataFrame
    pair_indices: list[tuple[int, int]]
    summary: MultiMatchSummary
    config: MultiMatchConfig
    left_name: str = "Dosya 1"
    right_name: str = "Dosya 2"

    def rules_as_rows(self) -> list[dict[str, object]]:
        rows = []
        for no, rule in enumerate(self.config.rules, 1):
            rows.append(
                {
                    "Kural": no,
                    "Dosya 1 Sütunu": rule.left_column,
                    "Operatör": operator_label(rule.operator),
                    "Dosya 2 Sütunu": rule.right_column,
                    "Veri Türü": rule.normalization.kind.value,
                    "Birincil": "Evet" if rule.primary else "Hayır",
                    "Boşlar Eşleşsin": "Evet" if rule.normalization.empty_matches_empty else "Hayır",
                    "Tolerans": str(rule.normalization.tolerance),
                }
            )
        return rows


def operator_label(operator: MatchOperator) -> str:
    return {
        MatchOperator.EQUALS: "Eşittir",
        MatchOperator.NUMERIC_TOLERANCE: "Sayısal tolerans",
        MatchOperator.DATE_TOLERANCE: "Tarih toleransı",
    }[operator]


class MatchingService:
    """Vektörel normalizasyon ve hash tabanlı kayıt eşleştirmesi."""

    @staticmethod
    def compare(
        reference_data: pd.DataFrame,
        reference_column: str,
        parking_data: pd.DataFrame,
        parking_column: str,
        progress: Callable[[int, str], None] | None = None,
    ) -> MatchResult:
        """Eski tek plaka akışını geriye uyumlu tutar."""
        if reference_column not in reference_data.columns:
            raise KeyError(f"Plaka listesi kolonu bulunamadı: {reference_column}")
        if parking_column not in parking_data.columns:
            raise KeyError(f"Otopark plaka kolonu bulunamadı: {parking_column}")
        if progress:
            progress(55, "Plakalar normalize ediliyor...")
        reference_normalized = normalize_plate_series(reference_data[reference_column])
        parking_normalized = normalize_plate_series(parking_data[parking_column])
        reference_set = set(reference_normalized[reference_normalized.ne("")].unique())
        if not reference_set:
            raise ValueError("Plaka listesinde karşılaştırılabilir bir plaka bulunamadı.")
        if progress:
            progress(70, "Plakalar karşılaştırılıyor...")
        match_series = parking_normalized.isin(reference_set)
        match_mask = match_series.to_numpy(dtype=bool, copy=True)
        matched_plates = parking_normalized[match_series & parking_normalized.ne("")]
        unmatched_plates = parking_normalized[~match_series & parking_normalized.ne("")]
        matched_count = int(match_mask.sum())
        total_count = int(len(parking_data))
        summary = MatchSummary(
            total_records=total_count,
            reference_plate_count=len(reference_set),
            matched_records=matched_count,
            unmatched_records=total_count - matched_count,
            matched_unique_plates=int(matched_plates.nunique()),
            unmatched_unique_plates=int(unmatched_plates.nunique()),
        )
        if progress:
            progress(90, "Sonuç hazırlanıyor...")
        return MatchResult(parking_data, match_mask, summary, parking_column)

    @classmethod
    def compare_multi(
        cls,
        left_data: pd.DataFrame,
        right_data: pd.DataFrame,
        config: MultiMatchConfig,
        left_name: str = "Dosya 1",
        right_name: str = "Dosya 2",
        progress: Callable[[int, str], None] | None = None,
    ) -> MultiMatchResult:
        cls._validate_rules(left_data, right_data, config.rules)
        if progress:
            progress(55, "Sütunlar normalize ediliyor...")

        normalized: list[tuple[pd.Series, pd.Series, MatchRule, ValueKind]] = []
        candidate_sets: list[list[list[int]] | None] = []
        for rule in config.rules:
            effective_rule = rule
            if rule.normalization.kind is ValueKind.AUTO:
                if rule.operator is MatchOperator.NUMERIC_TOLERANCE:
                    effective_rule = replace(
                        rule, normalization=replace(rule.normalization, kind=ValueKind.DECIMAL)
                    )
                elif rule.operator is MatchOperator.DATE_TOLERANCE:
                    effective_rule = replace(
                        rule, normalization=replace(rule.normalization, kind=ValueKind.DATETIME)
                    )
            left, kind = normalize_series(
                left_data[rule.left_column], effective_rule.normalization, rule.left_column
            )
            right, _ = normalize_series(
                right_data[rule.right_column], effective_rule.normalization, rule.right_column
            )
            normalized.append((left, right, effective_rule, kind))
            candidate_sets.append(None)

        if progress:
            progress(68, "Eşleştirme adayları hazırlanıyor...")
        exact_and = config.logic is LogicMode.AND and all(
            rule.operator is MatchOperator.EQUALS
            or (
                rule.operator is MatchOperator.NUMERIC_TOLERANCE
                and rule.normalization.tolerance == 0
            )
            or (
                rule.operator is MatchOperator.DATE_TOLERANCE
                and rule.normalization.date_tolerance_seconds == 0
            )
            for _, _, rule, _ in normalized
        )
        if exact_and:
            combined = cls._composite_candidates(normalized, len(left_data), len(right_data))
            primary_indices = [i for i, item in enumerate(normalized) if item[2].primary] or [0]
            for index in primary_indices:
                left, right, rule, kind = normalized[index]
                candidate_sets[index] = cls._rule_candidates(left, right, rule, kind)
        else:
            for index, (left, right, rule, kind) in enumerate(normalized):
                candidate_sets[index] = cls._rule_candidates(left, right, rule, kind)
            combined = cls._combine_candidates(
                [item for item in candidate_sets if item is not None],
                config.logic,
                len(left_data),
            )
        pairs = cls._select_pairs(combined, config)
        left_matched = {left for left, _ in pairs}
        right_matched = {right for _, right in pairs}
        left_unmatched_idx = [i for i in range(len(left_data)) if i not in left_matched]
        right_unmatched_idx = [i for i in range(len(right_data)) if i not in right_matched]

        if progress:
            progress(80, "Kısmi eşleşmeler analiz ediliyor...")
        partial = cls._build_partial_frame(
            left_data, right_data, normalized, candidate_sets, combined,
            left_unmatched_idx, right_unmatched_idx
        )
        matched_frame = cls._build_pair_frame(left_data, right_data, pairs, "Eşleşti")
        left_unmatched = cls._build_unmatched_frame(left_data, left_unmatched_idx, left_name)
        right_unmatched = cls._build_unmatched_frame(right_data, right_unmatched_idx, right_name)
        summary = MultiMatchSummary(
            len(left_data), len(right_data), len(pairs), len(left_unmatched_idx),
            len(right_unmatched_idx), len(partial),
        )
        if progress:
            progress(95, "Sonuç tabloları hazırlanıyor...")
        return MultiMatchResult(
            left_data, right_data, matched_frame, left_unmatched, right_unmatched,
            partial, pairs, summary, config, left_name, right_name,
        )

    @staticmethod
    def _validate_rules(left: pd.DataFrame, right: pd.DataFrame, rules: Iterable[MatchRule]) -> None:
        for rule in rules:
            if rule.left_column not in left.columns:
                raise KeyError(f"Dosya 1 sütunu bulunamadı: {rule.left_column}")
            if rule.right_column not in right.columns:
                raise KeyError(f"Dosya 2 sütunu bulunamadı: {rule.right_column}")

    @classmethod
    def _rule_candidates(
        cls, left: pd.Series, right: pd.Series, rule: MatchRule, kind: ValueKind
    ) -> list[list[int]]:
        tolerance = (
            rule.normalization.tolerance
            if rule.operator is MatchOperator.NUMERIC_TOLERANCE
            else pd.Timedelta(seconds=rule.normalization.date_tolerance_seconds)
        )
        if rule.operator is MatchOperator.EQUALS or tolerance == 0:
            lookup: dict[object, list[int]] = defaultdict(list)
            empty_right: list[int] = []
            for idx, value in enumerate(right.tolist()):
                if cls._missing(value):
                    empty_right.append(idx)
                else:
                    lookup[value].append(idx)
            output = []
            for value in left.tolist():
                if cls._missing(value):
                    output.append(empty_right.copy() if rule.normalization.empty_matches_empty else [])
                else:
                    # Aynı anahtarlı sol satırlar sağ aday listesini paylaşır;
                    # bu, tekrar kayıtlarında O(n²) bellek kullanımını önler.
                    output.append(lookup.get(value, []))
            return output

        valid = sorted((value, idx) for idx, value in enumerate(right.tolist()) if not cls._missing(value))
        values = [item[0] for item in valid]
        indices = [item[1] for item in valid]
        output: list[list[int]] = []
        for value in left.tolist():
            if cls._missing(value):
                output.append([])
                continue
            lo = bisect_left(values, value - tolerance)
            hi = bisect_right(values, value + tolerance)
            output.append(sorted(indices[lo:hi]))
        return output

    @staticmethod
    def _combine_candidates(
        candidate_sets: list[list[list[int]]], logic: LogicMode, left_count: int
    ) -> list[list[int]]:
        combined: list[list[int]] = []
        for left_index in range(left_count):
            sets = [set(rule_candidates[left_index]) for rule_candidates in candidate_sets]
            result = set.intersection(*sets) if logic is LogicMode.AND else set.union(*sets)
            combined.append(sorted(result))
        return combined

    @classmethod
    def _composite_candidates(
        cls,
        normalized: list[tuple[pd.Series, pd.Series, MatchRule, ValueKind]],
        left_count: int,
        right_count: int,
    ) -> list[list[int]]:
        """AND eşitliğini tek birleşik hash anahtarıyla O(n) zamanda çözer."""
        right_lookup: dict[tuple[object, ...], list[int]] = defaultdict(list)
        for right_index in range(right_count):
            key = cls._composite_key(normalized, right_index, use_left=False)
            if key is not None:
                right_lookup[key].append(right_index)
        output: list[list[int]] = []
        for left_index in range(left_count):
            key = cls._composite_key(normalized, left_index, use_left=True)
            output.append([] if key is None else right_lookup.get(key, []))
        return output

    @classmethod
    def _composite_key(
        cls,
        normalized: list[tuple[pd.Series, pd.Series, MatchRule, ValueKind]],
        row_index: int,
        use_left: bool,
    ) -> tuple[object, ...] | None:
        values: list[object] = []
        for rule_index, (left, right, rule, _) in enumerate(normalized):
            value = (left if use_left else right).iat[row_index]
            if cls._missing(value):
                if not rule.normalization.empty_matches_empty:
                    return None
                values.append(("__EMPTY__", rule_index))
            else:
                values.append(value)
        return tuple(values)

    @staticmethod
    def _select_pairs(candidates: list[list[int]], config: MultiMatchConfig) -> list[tuple[int, int]]:
        if config.duplicate_mode is DuplicateMode.ALL_MATCHES:
            count = sum(len(values) for values in candidates)
            if count > config.max_all_match_pairs:
                raise ValueError(
                    f"Tüm uygun eşleşmeler {count:,} çift üretecek. Güvenli sınır "
                    f"{config.max_all_match_pairs:,}; bire bir modu kullanın."
                )
            return [(left, right) for left, values in enumerate(candidates) for right in values]
        if config.duplicate_mode is DuplicateMode.UNIQUE_ONLY:
            right_counts = Counter(values[0] for values in candidates if len(values) == 1)
            group_counts = Counter(id(values) for values in candidates if values)
            return [
                (left, values[0]) for left, values in enumerate(candidates)
                if len(values) == 1
                and right_counts[values[0]] == 1
                and group_counts[id(values)] == 1
            ]
        used_right: set[int] = set()
        shared_cursors: dict[int, int] = {}
        pairs = []
        for left, values in enumerate(candidates):
            cursor = shared_cursors.get(id(values), 0)
            while cursor < len(values) and values[cursor] in used_right:
                cursor += 1
            shared_cursors[id(values)] = cursor + 1
            right = values[cursor] if cursor < len(values) else None
            if right is not None:
                pairs.append((left, right))
                used_right.add(right)
        return pairs

    @classmethod
    def _build_partial_frame(
        cls,
        left: pd.DataFrame,
        right: pd.DataFrame,
        normalized: list[tuple[pd.Series, pd.Series, MatchRule, ValueKind]],
        candidate_sets: list[list[list[int]] | None],
        full_candidates: list[list[int]],
        left_unmatched: list[int],
        right_unmatched: list[int],
    ) -> pd.DataFrame:
        columns = cls._pair_columns(left, right) + [
            "Eşleşen Kural Sayısı", "Farklı Kural Sayısı", "Kural Detayı", "Eşleşme Durumu"
        ]
        if len(normalized) < 2 or not left_unmatched or not right_unmatched:
            return pd.DataFrame(columns=columns)
        # Kısmi görünüm bir denetim görünümüdür; tam eşleşmede kullanılmış bir
        # sağ satır da başka bir sol satır için anlamlı bir kısmi aday olabilir.
        allowed_right = set(range(len(right)))
        primary_indices = [i for i, item in enumerate(normalized) if item[2].primary] or [0]
        rows: list[list[object]] = []
        for left_idx in left_unmatched:
            # Bir tam aday yalnızca bire-bir tüketim nedeniyle kullanılamadıysa
            # bu kayıt "kısmi" değildir; ikinci kez saymayız.
            if full_candidates[left_idx]:
                continue
            candidates: set[int] = set()
            for rule_idx in primary_indices:
                primary_candidates = candidate_sets[rule_idx]
                if primary_candidates is not None:
                    candidates.update(primary_candidates[left_idx])
            candidates &= allowed_right
            best: tuple[int, int, list[bool]] | None = None
            for right_idx in candidates:
                statuses = [
                    cls._values_match(lseries.iat[left_idx], rseries.iat[right_idx], rule)
                    for lseries, rseries, rule, _ in normalized
                ]
                score = sum(statuses)
                if score == 0 or score == len(statuses):
                    continue
                proposal = (score, -right_idx, statuses)
                if best is None or proposal[:2] > best[:2]:
                    best = proposal
            if best is None:
                continue
            right_idx = -best[1]
            statuses = best[2]
            detail = "; ".join(
                f"{rule.label()}: {'Eşleşti' if ok else 'Farklı'}"
                for ok, (_, _, rule, _) in zip(statuses, normalized, strict=True)
            )
            rows.append(
                cls._pair_values(left, right, left_idx, right_idx)
                + [sum(statuses), len(statuses) - sum(statuses), detail, "Kısmi Eşleşme"]
            )
        return pd.DataFrame(rows, columns=columns)

    @staticmethod
    def _values_match(left: object, right: object, rule: MatchRule) -> bool:
        left_missing = MatchingService._missing(left)
        right_missing = MatchingService._missing(right)
        if left_missing or right_missing:
            return bool(left_missing and right_missing and rule.normalization.empty_matches_empty)
        if rule.operator is MatchOperator.NUMERIC_TOLERANCE:
            return abs(left - right) <= rule.normalization.tolerance
        if rule.operator is MatchOperator.DATE_TOLERANCE:
            return abs(left - right) <= pd.Timedelta(seconds=rule.normalization.date_tolerance_seconds)
        return bool(left == right)

    @staticmethod
    def _missing(value: object) -> bool:
        if value is None or value is pd.NA or value is pd.NaT:
            return True
        try:
            return bool(pd.isna(value))
        except (TypeError, ValueError):
            return False

    @classmethod
    def _build_pair_frame(
        cls, left: pd.DataFrame, right: pd.DataFrame, pairs: list[tuple[int, int]], status: str
    ) -> pd.DataFrame:
        columns = cls._pair_columns(left, right) + ["Eşleşme Durumu"]
        if not pairs:
            return pd.DataFrame(columns=columns)
        left_indices = np.fromiter((pair[0] for pair in pairs), dtype=np.int64)
        right_indices = np.fromiter((pair[1] for pair in pairs), dtype=np.int64)
        left_part = left.iloc[left_indices].reset_index(drop=True).copy()
        left_part.columns = [f"Dosya 1 | {column}" for column in left.columns]
        left_part.insert(0, "Dosya 1 | Kaynak Satır", left_indices + 2)
        right_part = right.iloc[right_indices].reset_index(drop=True).copy()
        right_part.columns = [f"Dosya 2 | {column}" for column in right.columns]
        right_part.insert(0, "Dosya 2 | Kaynak Satır", right_indices + 2)
        result = pd.concat([left_part, right_part], axis=1)
        result["Eşleşme Durumu"] = status
        return result

    @staticmethod
    def _pair_columns(left: pd.DataFrame, right: pd.DataFrame) -> list[str]:
        return (
            ["Dosya 1 | Kaynak Satır"]
            + [f"Dosya 1 | {column}" for column in left.columns]
            + ["Dosya 2 | Kaynak Satır"]
            + [f"Dosya 2 | {column}" for column in right.columns]
        )

    @staticmethod
    def _pair_values(
        left: pd.DataFrame, right: pd.DataFrame, left_idx: int, right_idx: int
    ) -> list[object]:
        return [left_idx + 2, *left.iloc[left_idx].tolist(), right_idx + 2, *right.iloc[right_idx].tolist()]

    @staticmethod
    def _build_unmatched_frame(data: pd.DataFrame, indices: list[int], name: str) -> pd.DataFrame:
        result = data.iloc[indices].copy().reset_index(drop=True)
        result.insert(0, "Kaynak Satır", [idx + 2 for idx in indices])
        result["Eşleşme Durumu"] = f"{name} Eşleşmedi"
        return result
