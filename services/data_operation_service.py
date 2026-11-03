"""Excel verileri için güvenli, vektörel filtre ve hesaplama işlemleri."""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from utils.plate_utils import normalize_plate_series
from utils.value_normalizers import (
    NormalizationOptions,
    ValueKind,
    normalize_series,
    parse_decimal,
)


class DataOperationError(RuntimeError):
    """Kullanıcıya gösterilebilecek veri işlemi hatası."""


class FilterOperator(str, Enum):
    EMPTY = "empty"
    NOT_EMPTY = "not_empty"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER = "greater"
    GREATER_EQUAL = "greater_equal"
    LESS = "less"
    LESS_EQUAL = "less_equal"
    BETWEEN = "between"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN_LIST = "in_list"


FILTER_LABELS: dict[FilterOperator, str] = {
    FilterOperator.EMPTY: "Boş olan",
    FilterOperator.NOT_EMPTY: "Boş olmayan",
    FilterOperator.EQUALS: "Eşit",
    FilterOperator.NOT_EQUALS: "Eşit değil",
    FilterOperator.GREATER: "Büyük",
    FilterOperator.GREATER_EQUAL: "Büyük veya eşit",
    FilterOperator.LESS: "Küçük",
    FilterOperator.LESS_EQUAL: "Küçük veya eşit",
    FilterOperator.BETWEEN: "Arasında",
    FilterOperator.CONTAINS: "İçerir",
    FilterOperator.NOT_CONTAINS: "İçermez",
    FilterOperator.STARTS_WITH: "İle başlar",
    FilterOperator.ENDS_WITH: "İle biter",
    FilterOperator.IN_LIST: "Listede bulunan",
}


@dataclass(frozen=True)
class FilterCondition:
    column: str
    operator: FilterOperator
    value: str = ""
    second_value: str = ""


@dataclass
class OperationResult:
    dataframe: pd.DataFrame
    message: str
    scalar_label: str | None = None
    scalar_value: object | None = None


class DataOperationService:
    AGGREGATIONS = {
        "sum": "Toplam",
        "mean": "Ortalama",
        "median": "Medyan",
        "min": "Minimum",
        "max": "Maksimum",
        "count": "Dolu adet",
        "nunique": "Benzersiz adet",
        "std": "Standart sapma",
        "variance": "Varyans",
    }

    @classmethod
    def filter(
        cls,
        dataframe: pd.DataFrame,
        conditions: list[FilterCondition],
        logic: str = "and",
    ) -> OperationResult:
        if not conditions:
            raise DataOperationError("En az bir filtre kuralı ekleyin.")
        if logic not in {"and", "or"}:
            raise DataOperationError("Filtre mantığı AND veya OR olmalıdır.")
        combined = pd.Series(logic == "and", index=dataframe.index, dtype=bool)
        for condition in conditions:
            mask = cls._condition_mask(dataframe, condition)
            combined = combined & mask if logic == "and" else combined | mask
        result = dataframe.loc[combined].copy().reset_index(drop=True)
        return OperationResult(
            result,
            f"{len(dataframe):,} kayıttan {len(result):,} kayıt filtreye uydu.",
        )

    @classmethod
    def aggregate(
        cls, dataframe: pd.DataFrame, column: str, function: str
    ) -> OperationResult:
        cls._require_column(dataframe, column)
        if function not in cls.AGGREGATIONS:
            raise DataOperationError("Desteklenmeyen hesaplama türü.")
        series = dataframe[column]
        if function == "count":
            value: object = int((~cls._empty_mask(series)).sum())
        elif function == "nunique":
            value = int(series.loc[~cls._empty_mask(series)].nunique(dropna=True))
        else:
            values = [
                value
                for value in series.map(parse_decimal).tolist()
                if value is not pd.NA
            ]
            if not values:
                raise DataOperationError(
                    f"'{column}' sütununda hesaplanabilir sayısal değer bulunamadı."
                )
            if function == "sum":
                value = sum(values, Decimal("0"))
            elif function == "mean":
                value = sum(values, Decimal("0")) / Decimal(len(values))
            elif function == "median":
                value = statistics.median(values)
            elif function == "min":
                value = min(values)
            elif function == "max":
                value = max(values)
            elif function == "std":
                if len(values) < 2:
                    raise DataOperationError("Standart sapma için en az iki değer gerekir.")
                value = statistics.stdev(values)
            else:
                if len(values) < 2:
                    raise DataOperationError("Varyans için en az iki değer gerekir.")
                value = statistics.variance(values)
        label = f"{column} — {cls.AGGREGATIONS[function]}"
        return OperationResult(dataframe, f"{label} hesaplandı.", label, value)

    @classmethod
    def sort(
        cls, dataframe: pd.DataFrame, column: str, ascending: bool
    ) -> OperationResult:
        cls._require_column(dataframe, column)
        normalized, _kind = normalize_series(
            dataframe[column], NormalizationOptions(), column
        )
        try:
            order = normalized.sort_values(
                ascending=ascending, na_position="last", kind="mergesort"
            ).index
        except (TypeError, ValueError):
            order = normalized.astype("string").str.casefold().sort_values(
                ascending=ascending, na_position="last", kind="mergesort"
            ).index
        result = dataframe.loc[order]
        result = result.reset_index(drop=True)
        direction = "artan" if ascending else "azalan"
        return OperationResult(result, f"'{column}' sütunu {direction} sıralandı.")

    @classmethod
    def drop_missing(cls, dataframe: pd.DataFrame, column: str) -> OperationResult:
        cls._require_column(dataframe, column)
        mask = ~cls._empty_mask(dataframe[column])
        result = dataframe.loc[mask].copy().reset_index(drop=True)
        removed = len(dataframe) - len(result)
        return OperationResult(result, f"{removed:,} boş kayıt kaldırıldı.")

    @classmethod
    def fill_missing(
        cls, dataframe: pd.DataFrame, column: str, value: str
    ) -> OperationResult:
        cls._require_column(dataframe, column)
        result = dataframe.copy()
        mask = cls._empty_mask(result[column])
        count = int(mask.sum())
        result.loc[mask, column] = value
        return OperationResult(result, f"{count:,} boş hücre '{value}' ile dolduruldu.")

    @classmethod
    def remove_duplicates(
        cls, dataframe: pd.DataFrame, columns: list[str] | None, keep: str = "first"
    ) -> OperationResult:
        subset = columns or None
        if subset:
            for column in subset:
                cls._require_column(dataframe, column)
        if keep not in {"first", "last"}:
            raise DataOperationError("Tekrar saklama seçimi geçersiz.")
        result = dataframe.drop_duplicates(subset=subset, keep=keep).reset_index(drop=True)
        removed = len(dataframe) - len(result)
        return OperationResult(result, f"{removed:,} tekrar eden kayıt kaldırıldı.")

    @classmethod
    def transform_text(
        cls, dataframe: pd.DataFrame, column: str, operation: str
    ) -> OperationResult:
        cls._require_column(dataframe, column)
        if operation not in {"trim", "upper", "lower", "title"}:
            raise DataOperationError("Desteklenmeyen metin işlemi.")
        result = dataframe.copy()
        original = result[column]
        strings = original.astype("string")
        if operation == "trim":
            transformed = strings.str.strip()
            label = "boşlukları temizlendi"
        elif operation == "upper":
            transformed = strings.str.upper()
            label = "büyük harfe çevrildi"
        elif operation == "lower":
            transformed = strings.str.lower()
            label = "küçük harfe çevrildi"
        else:
            transformed = strings.str.title()
            label = "başlık biçimine çevrildi"
        result[column] = transformed.where(~original.isna(), original)
        return OperationResult(result, f"'{column}' sütununun {label}.")

    @classmethod
    def calculated_column(
        cls,
        dataframe: pd.DataFrame,
        left_column: str,
        operation: str,
        output_name: str,
        right_column: str | None = None,
        constant: str | None = None,
    ) -> OperationResult:
        cls._require_column(dataframe, left_column)
        output_name = output_name.strip()
        if not output_name:
            raise DataOperationError("Yeni sütun adını yazın.")
        if output_name in dataframe.columns:
            raise DataOperationError(f"'{output_name}' adlı sütun zaten var.")
        if operation == "concat":
            if not right_column:
                raise DataOperationError("Birleştirilecek ikinci sütunu seçin.")
            cls._require_column(dataframe, right_column)
            result = dataframe.copy()
            result[output_name] = (
                dataframe[left_column].astype("string").fillna("").str.strip()
                + " "
                + dataframe[right_column].astype("string").fillna("").str.strip()
            ).str.strip()
            return OperationResult(result, f"'{output_name}' metin sütunu oluşturuldu.")

        left = dataframe[left_column].map(parse_decimal)
        if right_column:
            cls._require_column(dataframe, right_column)
            right = dataframe[right_column].map(parse_decimal)
        else:
            parsed = parse_decimal(constant)
            if parsed is pd.NA:
                raise DataOperationError("Geçerli bir sayısal sabit yazın.")
            right = pd.Series([parsed] * len(dataframe), index=dataframe.index, dtype=object)
        valid = left.notna() & right.notna()
        output = pd.Series(pd.NA, index=dataframe.index, dtype=object)
        try:
            if operation == "add":
                output.loc[valid] = left.loc[valid] + right.loc[valid]
            elif operation == "subtract":
                output.loc[valid] = left.loc[valid] - right.loc[valid]
            elif operation == "multiply":
                output.loc[valid] = left.loc[valid] * right.loc[valid]
            elif operation == "divide":
                nonzero = valid & right.map(lambda value: value is not pd.NA and value != 0)
                output.loc[nonzero] = left.loc[nonzero] / right.loc[nonzero]
            elif operation == "percent":
                output.loc[valid] = left.loc[valid] * right.loc[valid] / Decimal("100")
            elif operation == "percent_change":
                nonzero = valid & right.map(lambda value: value is not pd.NA and value != 0)
                output.loc[nonzero] = (
                    (left.loc[nonzero] - right.loc[nonzero])
                    / right.loc[nonzero]
                    * Decimal("100")
                )
            else:
                raise DataOperationError("Desteklenmeyen hesaplanmış sütun işlemi.")
        except (ArithmeticError, TypeError) as exc:
            raise DataOperationError(f"Sütun hesaplanamadı: {exc}") from exc
        result = dataframe.copy()
        result[output_name] = output
        return OperationResult(result, f"'{output_name}' hesaplanmış sütunu oluşturuldu.")

    @classmethod
    def _condition_mask(
        cls, dataframe: pd.DataFrame, condition: FilterCondition
    ) -> pd.Series:
        cls._require_column(dataframe, condition.column)
        series = dataframe[condition.column]
        operator = condition.operator
        empty = cls._empty_mask(series)
        if operator == FilterOperator.EMPTY:
            return empty
        if operator == FilterOperator.NOT_EMPTY:
            return ~empty

        if operator in {
            FilterOperator.CONTAINS,
            FilterOperator.NOT_CONTAINS,
            FilterOperator.STARTS_WITH,
            FilterOperator.ENDS_WITH,
        }:
            values = series.astype("string").str.strip().str.casefold()
            needle = condition.value.strip().casefold()
            if not needle:
                raise DataOperationError("Filtre değeri boş olamaz.")
            if operator == FilterOperator.CONTAINS:
                return values.str.contains(needle, regex=False, na=False)
            if operator == FilterOperator.NOT_CONTAINS:
                return ~values.str.contains(needle, regex=False, na=False) & ~empty
            if operator == FilterOperator.STARTS_WITH:
                return values.str.startswith(needle, na=False)
            return values.str.endswith(needle, na=False)

        normalized, kind = normalize_series(
            series,
            NormalizationOptions(),
            condition.column,
        )
        if operator == FilterOperator.IN_LIST:
            raw_items = [
                item.strip()
                for item in re.split(r"[;,\n]+", condition.value)
                if item.strip()
            ]
            if not raw_items:
                raise DataOperationError("Liste filtresi için değerleri yazın.")
            items = [cls._normalize_scalar(item, kind) for item in raw_items]
            return normalized.isin(items) & normalized.notna()

        first = cls._normalize_scalar(condition.value, kind)
        if first is pd.NA or first is pd.NaT:
            raise DataOperationError("Filtre için geçerli bir değer yazın.")
        valid = normalized.notna()
        if operator == FilterOperator.EQUALS:
            return valid & normalized.eq(first)
        if operator == FilterOperator.NOT_EQUALS:
            return valid & normalized.ne(first)
        if operator == FilterOperator.GREATER:
            return valid & normalized.gt(first)
        if operator == FilterOperator.GREATER_EQUAL:
            return valid & normalized.ge(first)
        if operator == FilterOperator.LESS:
            return valid & normalized.lt(first)
        if operator == FilterOperator.LESS_EQUAL:
            return valid & normalized.le(first)
        if operator == FilterOperator.BETWEEN:
            second = cls._normalize_scalar(condition.second_value, kind)
            if second is pd.NA or second is pd.NaT:
                raise DataOperationError("Aralık için ikinci değeri yazın.")
            lower, upper = (first, second) if first <= second else (second, first)
            return valid & normalized.ge(lower) & normalized.le(upper)
        raise DataOperationError("Desteklenmeyen filtre operatörü.")

    @staticmethod
    def _normalize_scalar(value: str, kind: ValueKind) -> Any:
        if kind == ValueKind.DECIMAL:
            return parse_decimal(value)
        if kind in {ValueKind.DATE, ValueKind.DATETIME}:
            parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
            if pd.isna(parsed):
                return pd.NaT
            return parsed.normalize() if kind == ValueKind.DATE else parsed
        if kind == ValueKind.PLATE:
            return normalize_plate_series(pd.Series([value])).iat[0] or pd.NA
        text = value.strip().upper()
        return text or pd.NA

    @staticmethod
    def _empty_mask(series: pd.Series) -> pd.Series:
        return series.isna() | series.astype("string").str.strip().eq("").fillna(True)

    @staticmethod
    def _require_column(dataframe: pd.DataFrame, column: str) -> None:
        if column not in dataframe.columns:
            raise DataOperationError(f"Sütun bulunamadı: {column}")
