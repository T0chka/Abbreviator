import io
import json
import logging
import os
import secrets

from datetime import datetime, timedelta
from typing import Any, Dict, List, Union

from django.conf import settings
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.timezone import now
from django.views.decorators.http import require_http_methods
from docx import Document

from .model_integration.client import ModelClient
from .models import AbbreviationEntry
from .uploads import UploadValidationError, validate_docx_upload
from .utils import (
    Abbreviation,
    AbbreviationFormatter,
    AbbreviationTableExtractor,
    AbbreviationTableGenerator,
    compare_abbreviations,
    process_abbreviations,
)


DEMO_SESSION_ID = 'test_drive'

extractor = AbbreviationTableExtractor()
formatter = AbbreviationFormatter()
generator = AbbreviationTableGenerator()
logger = logging.getLogger('abb_app')


if not logger.hasHandlers():
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)


def generate_session_id() -> str:
    return secrets.token_urlsafe(9)


def cleanup_old_files(
    exclude_id: str,
    max_hours: int = settings.UPLOAD_RETENTION_HOURS
) -> None:
    """Remove expired uploaded documents while preserving the demo file."""
    fs = FileSystemStorage()
    current_time = datetime.now()

    for filename in fs.listdir('')[1]:
        if filename.startswith(exclude_id):
            continue

        file_path = fs.path(filename)
        modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        if current_time - modified > timedelta(hours=max_hours):
            fs.delete(filename)


def upload_page_context(**extra: Any) -> Dict[str, Any]:
    return {
        'demo_session_id': DEMO_SESSION_ID,
        'max_upload_size': settings.MAX_UPLOAD_SIZE,
        'max_upload_size_mb': settings.MAX_UPLOAD_SIZE_MB,
        **extra,
    }


def upload_error_response(
    request: HttpRequest,
    message: str,
    status_code: int = 400
) -> HttpResponse:
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': message}, status=status_code)

    return render(
        request,
        'upload.html',
        upload_page_context(error=message),
        status=status_code
    )


@require_http_methods(['GET', 'POST'])
def upload_file(request: HttpRequest) -> HttpResponse:
    if request.method == 'GET':
        request.session.flush()
        return render(
            request,
            'upload.html',
            upload_page_context()
        )

    uploaded_file = request.FILES.get('uploaded_file')
    if uploaded_file is None:
        return upload_error_response(
            request,
            'Файл не выбран.'
        )

    try:
        validate_docx_upload(uploaded_file)
    except UploadValidationError as exc:
        return upload_error_response(
            request,
            str(exc),
            status_code=exc.status_code
        )

    cleanup_old_files(exclude_id=DEMO_SESSION_ID)

    size_mb = uploaded_file.size / (1024 * 1024)
    logger.info(
        'Uploading file: %s, size: %.1f MB',
        uploaded_file.name,
        size_mb
    )

    requested_id = generate_session_id()
    filename = FileSystemStorage().save(
        f'{requested_id}.docx',
        uploaded_file
    )
    session_id = os.path.splitext(filename)[0]
    request.session['uploaded_file_path'] = filename

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'session_id': session_id})

    return redirect(
        'process_file_with_session',
        session_id=session_id
    )


@require_http_methods(['GET'])
def process_file_with_session(
    request: HttpRequest,
    session_id: str
) -> HttpResponse:
    fs = FileSystemStorage()

    if session_id == DEMO_SESSION_ID:
        filenames = [
            name for name in fs.listdir('')[1]
            if name.startswith(DEMO_SESSION_ID)
            and name.lower().endswith('.docx')
        ]
        filename = filenames[0] if filenames else None
    else:
        filename = f'{session_id}.docx'
        if not fs.exists(filename):
            filename = None

    if filename:
        request.session['uploaded_file_path'] = filename
        return process_and_display(request)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'error'}, status=404)

    messages.error(request, 'Сессия не найдена или истекла')
    return redirect('upload_file')


def parse_request_json(request: HttpRequest) -> Dict[str, Any]:
    data: Dict[str, Any] = json.loads(request.body)
    if not data:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    return data


def get_processed_doc_abbs(request: HttpRequest) -> List[Dict[str, Any]]:
    """
    Extract abbreviations with user-selected descriptions from the session.
    """
    doc_abbs = request.session.get('doc_abbs', [])
    return [
        {
            'abbreviation': abb['abbreviation'],
            'description': abb['selected_description']
        }
        for abb in doc_abbs
        if abb.get('selected_description') is not None
    ]


@require_http_methods(['POST'])
def update_difference_section(request: HttpRequest) -> HttpResponse:
    initial_abbs: List[Abbreviation] = request.session.get(
        'initial_abbs',
        []
    )
    processed_doc_abbs = get_processed_doc_abbs(request)

    if not processed_doc_abbs and not initial_abbs:
        return render(request, 'partials/differences_section.html')

    if not processed_doc_abbs:
        return render(
            request,
            'partials/differences_section.html',
            {'missing_abbs': initial_abbs}
        )

    if not initial_abbs:
        return render(
            request,
            'partials/differences_section.html',
            {'new_found': processed_doc_abbs}
        )

    changes = compare_abbreviations(
        old_abbs=initial_abbs,
        new_abbs=processed_doc_abbs
    )
    return render(
        request,
        'partials/differences_section.html',
        {
            'missing_abbs': changes.get('missing_abbs', []),
            'new_found': changes.get('new_found', []),
        }
    )


def update_abbreviation(request: HttpRequest) -> JsonResponse:
    data = parse_request_json(request)

    abb = data.get('abbreviation')
    description = data.get('description')
    action = data.get('action')

    doc_abbs: List[Abbreviation] = request.session.get('doc_abbs', [])
    abb_entry = next(
        (entry for entry in doc_abbs if entry['abbreviation'] == abb),
        None
    )

    if action == 'add':
        abb_entry['selected_description'] = description

        logger.debug('Added abb_entry: %s', abb_entry)
        if description not in abb_entry['descriptions']:
            correct_form = abb_entry.get('correct_form')
            AbbreviationEntry.objects.create(
                abbreviation=correct_form if correct_form is not None else abb,
                description=description,
                status='for_review',
                highlighted=abb_entry.get('highlighted')
            )
            logger.debug('New entry for review: %s', abb_entry)
    elif action == 'skip':
        abb_entry['selected_description'] = None

    request.session['doc_abbs'] = doc_abbs
    return JsonResponse({'success': True})


def load_abbreviation_dict() -> List[Abbreviation]:
    """Load approved abbreviations from the database."""
    approved_entries = AbbreviationEntry.objects.filter(
        status='approved'
    ).values('abbreviation', 'description')

    abb_dict: Dict[str, List[str]] = {}
    for entry in approved_entries:
        abb = entry['abbreviation']
        description = entry['description']
        abb_dict.setdefault(abb, []).append(description)

    return [
        {
            'abbreviation': abb,
            'descriptions': descriptions
        }
        for abb, descriptions in abb_dict.items()
    ]


def process_and_display(request: HttpRequest) -> HttpResponse:
    file_name = request.session.get('uploaded_file_path')
    if not file_name:
        return render(
            request,
            'upload.html',
            upload_page_context(
                error='Пожалуйста, загрузите новый файл.'
            )
        )

    request.session.clear()
    request.session['uploaded_file_path'] = file_name

    file_path = FileSystemStorage().path(file_name)
    logger.debug('Processing file: %s', file_path)

    abb_dict = load_abbreviation_dict()
    logger.debug(
        'Loaded abbreviation dictionary: %s',
        len(abb_dict)
    )

    doc = Document(file_path)
    initial_abbs = extractor.get_abbreviation_table(doc)
    doc_abbs: List[Abbreviation] = process_abbreviations(doc, abb_dict)

    request.session['doc_abbs'] = doc_abbs
    request.session['initial_abbs'] = initial_abbs

    return render(
        request,
        'content.html',
        {
            'doc_abbs': doc_abbs,
            'has_initial_abbs': bool(initial_abbs),
            'initial_abbs_count': len(initial_abbs),
        }
    )


@require_http_methods(['POST'])
def make_abbreviation_table(
    request: HttpRequest
) -> Union[HttpResponse, JsonResponse]:
    try:
        processed_doc_abbs = get_processed_doc_abbs(request)

        if not processed_doc_abbs:
            return JsonResponse(
                {
                    'success': False,
                    'error': 'Нет аббревиатур для генерации таблицы'
                },
                status=400
            )

        processed_doc_abbs = formatter.clean_and_sort_abbreviations(
            processed_doc_abbs
        )
        file_stream = io.BytesIO()
        doc = generator.generate_document(processed_doc_abbs)
        doc.save(file_stream)
        file_stream.seek(0)

        response = HttpResponse(
            file_stream.getvalue(),
            content_type=(
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            )
        )
        response['Content-Disposition'] = (
            'attachment; filename=abbreviation_table.docx'
        )
        return response

    except Exception as exc:
        logger.error('Failed to generate table', exc_info=True)
        return JsonResponse(
            {
                'success': False,
                'error': str(exc)
            },
            status=500
        )


@require_http_methods(['GET'])
def dictionary_view(request: HttpRequest) -> HttpResponse:
    """Public view of the abbreviation dictionary."""
    abbreviations = AbbreviationEntry.objects.filter(
        status='approved'
    ).order_by('abbreviation')

    total_count = abbreviations.count()
    last_month = now() - timedelta(days=30)
    new_count = abbreviations.filter(
        created_at__gte=last_month
    ).count()
    last_entry = abbreviations.order_by('-created_at').first()
    last_update = last_entry.created_at if last_entry else None

    return render(
        request,
        'dictionary.html',
        {
            'abbreviations': abbreviations,
            'total_count': total_count,
            'new_count': new_count,
            'last_update': last_update,
        }
    )


@require_http_methods(['POST'])
def generate_description(request: HttpRequest) -> JsonResponse:
    """Generate description for abbreviation using LLM."""
    try:
        data = parse_request_json(request)
        abb = data.get('abbreviation')
        context = data.get('context', '')

        if not abb:
            return JsonResponse(
                {
                    'success': False,
                    'error': 'Abbreviation is required'
                },
                status=400
            )

        client = ModelClient(
            host=settings.OLLAMA_HOST,
            model=settings.OLLAMA_MODEL,
            temperature=0.6,
            top_p=0.6
        )

        prompt = (
            "Расшифруй аббревиатуру, следуя этим важным правилам:\n"
            "1. Расшифровка должна быть максимально короткой и "
            "соответствовать контексту.\n"
            "2. Слова в расшифровке должны соответствовать буквам "
            "аббревиатуры.\n"
            "3. Язык расшифровки должен соответствовать языку "
            "аббревиатуры.\n"
            "4. Если не уверен, что расшифровка правильная, то отвечай "
            "'не знаю'.\n"
            f"\nАббревиатура: '{abb}'\n"
            f"Контекст использования: '{context}'\n"
            "Дай ответ в формате JSON с полем 'description'."
        )

        description = client.generate_response(prompt)

        unavailable = (
            'Sorry, the language model service is unavailable now'
        )
        if description == unavailable:
            return JsonResponse(
                {
                    'success': False,
                    'error': 'The language model service is unavailable',
                    'description': description
                }
            )

        return JsonResponse(
            {
                'success': True,
                'description': description
            }
        )

    except Exception as exc:
        logger.error(
            'Failed to generate description',
            exc_info=True
        )
        return JsonResponse(
            {
                'success': False,
                'error': str(exc)
            },
            status=500
        )
