"""Kaynak Excel dosyalarını salt okunur biçimde yükleme servisi."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd


class ExcelServiceError(RuntimeError):
    """Kullanıcıya gösterilebilecek Excel okuma hatası."""


class ExcelService:
    """Excel başlıklarını ve verilerini kaynak dosyayı değiştirmeden okur."""

    SUPPORTED_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".csv"}

    @classmethod
    def validate_path(cls, path: str | Path) -> Path:
        file_path = Path(path)
        if not file_path.exists() or not file_path.is_file():
            raise ExcelServiceError("Seçilen Excel dosyası bulunamadı.")
        if file_path.suffix.lower() not in cls.SUPPORTED_SUFFIXES:
            raise ExcelServiceError(
                "Desteklenmeyen dosya türü. .xlsx, .xlsm, .xls veya .csv seçin."
            )
        return file_path

    @staticmethod
    def _engine_for(path: Path) -> str:
        return "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"

    @classmethod
    def list_sheets(cls, path: str | Path) -> list[str]:
        """Dosyadaki çalışma sayfalarını kaynak dosyayı değiştirmeden listeler."""
        file_path = cls.validate_path(path)
        if file_path.suffix.lower() == ".csv":
            return ["CSV"]
        try:
            with pd.ExcelFile(file_path, engine=cls._engine_for(file_path)) as book:
                sheets = list(book.sheet_names)
        except PermissionError as exc:
            raise ExcelServiceError(
                "Excel dosyasına erişilemiyor. Dosyanın açık veya kilitli olmadığını kontrol edin."
            ) from exc
        except Exception as exc:
            raise ExcelServiceError(f"Excel sayfaları okunamadı: {exc}") from exc
        if not sheets:
            raise ExcelServiceError("Excel dosyasında çalışma sayfası bulunamadı.")
        return sheets

    @classmethod
    def read_columns(
        cls, path: str | Path, sheet_name: str | int | None = None
    ) -> tuple[str, list[str]]:
        """Seçilen çalışma sayfasının adını ve kolon başlıklarını döndürür."""
        file_path = cls.validate_path(path)
        try:
            if file_path.suffix.lower() == ".csv":
                header = cls._read_csv(file_path, nrows=0)
                columns = [str(column).strip() for column in header.columns]
                if not columns:
                    raise ExcelServiceError("CSV dosyası boş veya başlık satırı bulunamadı.")
                return "CSV", columns
            with pd.ExcelFile(file_path, engine=cls._engine_for(file_path)) as book:
                if not book.sheet_names:
                    raise ExcelServiceError("Excel dosyasında çalışma sayfası bulunamadı.")
                selected_sheet = book.sheet_names[0] if sheet_name is None else sheet_name
                if isinstance(selected_sheet, str) and selected_sheet not in book.sheet_names:
                    raise ExcelServiceError(f"Çalışma sayfası bulunamadı: {selected_sheet}")
                header = book.parse(sheet_name=selected_sheet, nrows=0)
                if isinstance(selected_sheet, int):
                    selected_sheet = book.sheet_names[selected_sheet]
        except ExcelServiceError:
            raise
        except PermissionError as exc:
            raise ExcelServiceError(
                "Excel dosyasına erişilemiyor. Dosyanın açık veya kilitli olmadığını kontrol edin."
            ) from exc
        except Exception as exc:
            raise ExcelServiceError(f"Excel dosyası açılamadı: {exc}") from exc

        columns = [str(column).strip() for column in header.columns]
        if not columns:
            raise ExcelServiceError("Excel dosyası boş veya başlık satırı bulunamadı.")
        return str(selected_sheet), columns

    @classmethod
    def read_dataframe(
        cls,
        path: str | Path,
        progress: Callable[[int, str], None] | None = None,
        progress_value: int = 0,
        message: str = "Excel okunuyor...",
        sheet_name: str | int = 0,
    ) -> pd.DataFrame:
        """İlk çalışma sayfasını DataFrame olarak yükler.

        ``dtype=object`` kaynak hücrelerin metin, sayı ve tarih türlerini mümkün
        olduğunca korur. Kaynak dosya hiçbir zaman yazma modunda açılmaz.
        """
        file_path = cls.validate_path(path)
        if progress:
            progress(progress_value, message)
        try:
            if file_path.suffix.lower() == ".csv":
                dataframe = cls._read_csv(file_path, dtype=object)
            else:
                dataframe = pd.read_excel(
                    file_path,
                    sheet_name=sheet_name,
                    dtype=object,
                    engine=cls._engine_for(file_path),
                )
        except PermissionError as exc:
            raise ExcelServiceError(
                f"{file_path.name} dosyasına erişilemiyor. Dosya başka bir programda açık olabilir."
            ) from exc
        except ImportError as exc:
            if file_path.suffix.lower() == ".xls":
                raise ExcelServiceError(
                    ".xls dosyalarını okumak için xlrd paketi gereklidir. "
                    "requirements.txt bağımlılıklarını yeniden yükleyin."
                ) from exc
            raise ExcelServiceError(f"Excel okuma bileşeni eksik: {exc}") from exc
        except Exception as exc:
            raise ExcelServiceError(
                f"{file_path.name} okunamadı. Dosya bozuk veya desteklenmeyen bir yapıda olabilir: {exc}"
            ) from exc

        if dataframe.empty and len(dataframe.columns) == 0:
            raise ExcelServiceError(f"{file_path.name} tamamen boş.")
        if dataframe.empty:
            raise ExcelServiceError(f"{file_path.name} veri satırı içermiyor.")
        return dataframe

    @staticmethod
    def _read_csv(path: Path, **kwargs: object) -> pd.DataFrame:
        """Türkçe Windows CSV'lerinde ayırıcı ve kodlamayı güvenli biçimde algılar."""
        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "cp1254", "latin1"):
            try:
                return pd.read_csv(
                    path,
                    sep=None,
                    engine="python",
                    encoding=encoding,
                    **kwargs,
                )
            except UnicodeDecodeError as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise ExcelServiceError("CSV dosyası okunamadı.")
