"""Sütun bazlı, güvenli karşılaştırma normalizasyonları."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

import pandas as pd

from utils.plate_utils import normalize_plate_series


class ValueKind(str, Enum):
    AUTO = "auto"
    TEXT = "text"
    PLATE = "plate"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"


@dataclass(slots=True, frozen=True)
class NormalizationOptions:
    kind: ValueKind = ValueKind.AUTO
    trim: bool = True
    case_insensitive: bool = True
    remove_internal_spaces: bool = False
    empty_matches_empty: bool = False
    tolerance: Decimal = Decimal("0")
    date_tolerance_seconds: int = 0


def normalize_series(
    series: pd.Series,
    options: NormalizationOptions,
    column_name: str = "",
) -> tuple[pd.Series, ValueKind]:
    kind = options.kind
    if kind is ValueKind.AUTO:
        kind = infer_value_kind(series, column_name)

    if kind is ValueKind.PLATE:
        normalized = normalize_plate_series(series).replace("", pd.NA)
    elif kind is ValueKind.DECIMAL:
        normalized = series.map(parse_decimal)
    elif kind in {ValueKind.DATE, ValueKind.DATETIME}:
        parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
        normalized = parsed.dt.normalize() if kind is ValueKind.DATE else parsed
    else:
        normalized = normalize_text_series(series, options)
    return normalized, kind


def infer_value_kind(series: pd.Series, column_name: str = "") -> ValueKind:
    folded = _fold(column_name)
    if any(word in folded for word in ("plaka", "plate", "arac no")):
        return ValueKind.PLATE
    if any(word in folded for word in ("tarih", "date", "zaman", "saat")):
        return ValueKind.DATETIME if "saat" in folded or "zaman" in folded else ValueKind.DATE
    if any(word in folded for word in ("tutar", "ucret", "fiyat", "bedel", "odeme", "tahsil")):
        return ValueKind.DECIMAL
    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        return ValueKind.DATETIME
    if pd.api.types.is_numeric_dtype(series.dtype):
        return ValueKind.DECIMAL
    return ValueKind.TEXT


def normalize_text_series(series: pd.Series, options: NormalizationOptions) -> pd.Series:
    result = series.astype("string")
    if options.trim:
        result = result.str.strip()
    if options.remove_internal_spaces:
        result = result.str.replace(r"\s+", "", regex=True)
    if options.case_insensitive:
        result = result.str.upper()
    return result.replace("", pd.NA)


def parse_decimal(value: Any) -> Decimal | pd._libs.missing.NAType:
    if value is None or value is pd.NA or value is pd.NaT:
        return pd.NA
    try:
        if pd.isna(value):
            return pd.NA
    except (TypeError, ValueError):
        pass
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))

    text = str(value).strip()
    if not text:
        return pd.NA
    text = re.sub(r"[^0-9,\.\-+]", "", text)
    if text in {"", "+", "-"}:
        return pd.NA

    comma = text.rfind(",")
    dot = text.rfind(".")
    if comma >= 0 and dot >= 0:
        decimal_sep = "," if comma > dot else "."
        thousands_sep = "." if decimal_sep == "," else ","
        text = text.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif comma >= 0:
        parts = text.split(",")
        text = "".join(parts[:-1]) + "." + parts[-1] if len(parts[-1]) <= 2 else "".join(parts)
    elif dot >= 0:
        parts = text.split(".")
        if len(parts) > 2:
            text = "".join(parts[:-1]) + "." + parts[-1] if len(parts[-1]) <= 2 else "".join(parts)
        elif len(parts[-1]) == 3:
            text = "".join(parts)
    try:
        return Decimal(text)
    except InvalidOperation:
        return pd.NA


def _fold(value: str) -> str:
    value = value.replace("İ", "I").replace("ı", "i")
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()
