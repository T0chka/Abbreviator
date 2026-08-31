import os
import time

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import HttpRequest


DEMO_FILENAME = 'test_drive.docx'
SESSION_FILE_KEY = 'uploaded_file_path'
PROCESSED_FILE_SESSION_KEY = 'processed_file_path'
TABLE_CHECK_SESSION_KEY = 'table_check_enabled'
WORKFLOW_STATE_SESSION_KEY = 'workflow_tools_open'
CARD_STATE_SESSION_KEY = 'collapsed_abbreviations'


def clear_processing_state(request: HttpRequest) -> None:
    for key in (
        PROCESSED_FILE_SESSION_KEY,
        'doc_abbs',
        'initial_abbs',
        TABLE_CHECK_SESSION_KEY,
        WORKFLOW_STATE_SESSION_KEY,
        CARD_STATE_SESSION_KEY,
    ):
        request.session.pop(key, None)


def delete_session_document(request: HttpRequest) -> None:
    filename = request.session.pop(SESSION_FILE_KEY, None)
    if filename and filename != DEMO_FILENAME:
        FileSystemStorage().delete(filename)


def refresh_document_session(request: HttpRequest) -> None:
    request.session.set_expiry(settings.DOCUMENT_SESSION_TIMEOUT_SECONDS)

    filename = request.session.get(SESSION_FILE_KEY)
    if not filename or filename == DEMO_FILENAME:
        return

    fs = FileSystemStorage()
    if fs.exists(filename):
        os.utime(fs.path(filename), None)


def cleanup_expired_documents() -> int:
    fs = FileSystemStorage()
    cutoff = time.time() - settings.DOCUMENT_SESSION_TIMEOUT_SECONDS
    deleted = 0

    for filename in fs.listdir('')[1]:
        if filename == DEMO_FILENAME or not filename.lower().endswith('.docx'):
            continue

        if os.path.getmtime(fs.path(filename)) <= cutoff:
            fs.delete(filename)
            deleted += 1

    return deleted
