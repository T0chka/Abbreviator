from pathlib import Path
from zipfile import BadZipFile, LargeZipFile, ZipFile

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile


DOCX_REQUIRED_PARTS = {
    '[Content_Types].xml',
    'word/document.xml',
}


class UploadValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def format_megabytes(size: int) -> str:
    value = size / (1024 * 1024)
    return f'{value:.1f}'.replace('.', ',')


def validate_docx_upload(uploaded_file: UploadedFile) -> None:
    if Path(uploaded_file.name).suffix.lower() != '.docx':
        raise UploadValidationError(
            'Можно загрузить только файл формата .docx.'
        )

    if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
        actual_size = format_megabytes(uploaded_file.size)
        raise UploadValidationError(
            f'Файл слишком большой: {actual_size} МБ. '
            f'Максимальный размер: {settings.MAX_UPLOAD_SIZE_MB} МБ.',
            status_code=413
        )

    try:
        uploaded_file.seek(0)
        with ZipFile(uploaded_file) as archive:
            names = set(archive.namelist())
            if not DOCX_REQUIRED_PARTS.issubset(names):
                raise UploadValidationError(
                    'Не удалось открыть документ. '
                    'Загрузите корректный файл .docx.'
                )

            unpacked_size = sum(
                item.file_size for item in archive.infolist()
            )
            if unpacked_size > settings.MAX_DOCX_UNCOMPRESSED_SIZE:
                raise UploadValidationError(
                    'Документ слишком большой для обработки.'
                )
    except (BadZipFile, LargeZipFile):
        raise UploadValidationError(
            'Не удалось открыть документ. '
            'Загрузите корректный файл .docx.'
        )
    finally:
        uploaded_file.seek(0)
