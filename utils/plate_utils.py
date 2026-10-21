"""Plaka normalizasyonu ve plaka kolonu tahmini yardımcıları."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

import pandas as pd


_TURKISH_TRANSLATION = str.maketrans(
    {
        "Ç": "C",
        "Ğ": "G",
        "İ": "I",
        "I": "I",
        "Ö": "O",
        "Ş": "S",
        "Ü": "U",
    }
)


def normalize_plate_series(series: pd.Series) -> pd.Series:
    """Plakaları özgün kolonu değiştirmeden vektörel olarak normalize eder.

    Boşluklar, tireler, noktalar ve benzeri ayraçlar yok sayılır. Türkçe
    harfler ASCII karşılıklarına dönüştürülür. Sonuç pandas ``string``
    tipindedir; eksik değerler boş metin olur.
    """
    normalized = series.astype("string").fillna("")
    normalized = normalized.str.strip().str.upper()
    normalized = normalized.str.replace(r"\.0+$", "", regex=True)
    normalized = normalized.str.translate(_TURKISH_TRANSLATION)
    normalized = normalized.str.replace(r"[^0-9A-Z]", "", regex=True)
    return normalized


def normalize_header(value: object) -> str:
    """Kolon başlığını tahmin amacıyla sadeleştirir."""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def guess_plate_column(columns: Iterable[object]) -> int:
    """Plaka olma olasılığı en yüksek kolonun indeksini döndürür.

    Uygun kolon bulunamazsa ``-1`` döner.
    """
    normalized = [normalize_header(column) for column in columns]
    exact_names = (
        "plaka",
        "aracplaka",
        "aracplakasi",
        "aracplakano",
        "plate",
        "platenumber",
        "licenseplate",
        "vehicleplate",
        "registrationplate",
    )
    for candidate in exact_names:
        if candidate in normalized:
            return normalized.index(candidate)

    for index, name in enumerate(normalized):
        if "plaka" in name or "licenseplate" in name or name.endswith("plate"):
            return index
    return -1
