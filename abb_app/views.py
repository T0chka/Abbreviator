import json
import logging
import os
import secrets

from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.timezone import now
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import AbbreviationEntry
from .services.abbreviations import (
    Abbreviation,
    compare_abbreviations,
    update_abbreviation_selection,
)
from .services.documents import (
    build_abbreviation_table_docx,
    prepare_abbreviation_table_entries,
    process_document,
)
from .services.extraction import CharacterValidator
from .services.llm import (
    LLMServiceError,
    generate_abbreviation_description,
)
from .services.sessions import (
    DEMO_FILENAME,
    PROCESSED_FILE_SESSION_KEY,
    SESSION_FILE_KEY,
    TABLE_CHECK_SESSION_KEY,
    WORKFLOW_STATE_SESSION_KEY,
    delete_session_document,
    refresh_document_session,
)
from .services.uploads import UploadValidationError, validate_docx_upload


DEMO_SESSION_ID = 'test_drive'

logger = logging.getLogger(__name__)

CONTEXT_LIMITS = {1, 3, 5, 10}
CONTEXT_WINDOWS = {25, 50, 75, 100, 150}
TABLE_SORT_MODES = {'alphabetical', 'appearance'}
TABLE_SCRIPT_ORDERS = {'cyrillic_first', 'latin_first'}
TABLE_SCOPES = {'all', 'new'}
WORKFLOW_TOOL_IDS = {'comparison-block', 'table-preview-tool'}


def parse_context_limit(value: Any) -> Optional[int]:
    if value is None:
        return 3
    if value == 'all':
        return None
    if type(value) is int and value in CONTEXT_LIMITS:
        return value
    raise ValueError('Invalid context limit')


def parse_context_window(value: Any) -> int:
    if value is None:
        return 50
    if type(value) is int and value in CONTEXT_WINDOWS:
        return value
    raise ValueError('Invalid context window')


def trim_context(
    context: str,
    abbreviation: str,
    window: int,
) -> str:
    has_leading_ellipsis = context.startswith('...')
    has_trailing_ellipsis = context.endswith('...')
    start_offset = 3 if has_leading_ellipsis else 0
    end_offset = -3 if has_trailing_ellipsis else None
    core = context[start_offset:end_offset].strip()
    abbreviation_index = core.find(abbreviation)

    if abbreviation_index < 0:
        return context

    start = max(0, abbreviation_index - window)
    end = min(
        len(core),
        abbreviation_index + len(abbreviation) + window,
    )
    prefix = '...' if has_leading_ellipsis or start > 0 else ''
    suffix = '...' if has_trailing_ellipsis or end < len(core) else ''
    return f'{prefix}{core[start:end].strip()}{suffix}'


def parse_table_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    sort_mode = data.get('sort_mode', 'alphabetical')
    script_order = data.get('script_order', 'latin_first')
    scope = data.get('scope', 'all')
    use_correct_form = data.get('use_correct_form', True)

    if sort_mode not in TABLE_SORT_MODES:
        raise ValueError('Invalid table sort mode')
    if script_order not in TABLE_SCRIPT_ORDERS:
        raise ValueError('Invalid script order')
    if scope not in TABLE_SCOPES:
        raise ValueError('Invalid table scope')
    if not isinstance(use_correct_form, bool):
        raise ValueError('Invalid correct-form setting')

    return {
        'sort_mode': sort_mode,
        'script_order': script_order,
        'scope': scope,
        'use_correct_form': use_correct_form,
    }


def generate_session_id() -> str:
    return secrets.token_urlsafe(9)


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
        delete_session_document(request)
        request.session.flush()
        return render(
            request,
            'upload.html',
            upload_page_context(
                session_expired=request.GET.get('expired') == '1'
            )
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

    delete_session_document(request)
    request.session.pop(PROCESSED_FILE_SESSION_KEY, None)
    request.session.pop('doc_abbs', None)
    request.session.pop('initial_abbs', None)
    request.session.pop(TABLE_CHECK_SESSION_KEY, None)
    request.session.pop(WORKFLOW_STATE_SESSION_KEY, None)

    requested_id = generate_session_id()
    filename = FileSystemStorage().save(
        f'{requested_id}.docx',
        uploaded_file
    )
    session_id = os.path.splitext(filename)[0]
    request.session[SESSION_FILE_KEY] = filename
    refresh_document_session(request)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'session_id': session_id})

    return redirect(
        'process_file_with_session',
        session_id=session_id
    )


@require_http_methods(['GET'])
def download_demo_document(_request: HttpRequest) -> FileResponse:
    return FileResponse(
        FileSystemStorage().open(DEMO_FILENAME, 'rb'),
        as_attachment=True,
        filename='abbreviator_demo.docx'
    )


@require_http_methods(['POST'])
def touch_document_session(request: HttpRequest) -> HttpResponse:
    refresh_document_session(request)
    return HttpResponse(status=204)


@require_http_methods(['POST'])
def end_document_session(request: HttpRequest) -> HttpResponse:
    delete_session_document(request)
    request.session.flush()
    return HttpResponse(status=204)


@ensure_csrf_cookie
@require_http_methods(['GET'])
def process_file_with_session(
    request: HttpRequest,
    session_id: str
) -> HttpResponse:
    fs = FileSystemStorage()
    is_demo = session_id == DEMO_SESSION_ID
    filename = DEMO_FILENAME if is_demo else f'{session_id}.docx'

    session_filename = request.session.get(SESSION_FILE_KEY)
    if not is_demo and (
        session_filename != filename or not fs.exists(filename)
    ):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error'}, status=404)

        messages.error(request, 'Сессия не найдена или истекла')
        return redirect('upload_file')

    request.session[SESSION_FILE_KEY] = filename
    return process_and_display(request, is_demo=is_demo)


def parse_request_json(request: HttpRequest) -> Dict[str, Any]:
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError('Invalid JSON') from exc

    if not isinstance(data, dict):
        raise ValueError('JSON object expected')

    return data


def parse_optional_json_body(request: HttpRequest) -> Dict[str, Any]:
    if request.content_type != 'application/json' or not request.body:
        return {}
    return parse_request_json(request)


@require_http_methods(['POST'])
def update_difference_section(request: HttpRequest) -> HttpResponse:
    try:
        table_settings = parse_table_settings(
            parse_optional_json_body(request)
        )
    except ValueError as exc:
        return JsonResponse(
            {'success': False, 'error': str(exc)},
            status=400,
        )

    initial_abbs: List[Abbreviation] = request.session.get(
        'initial_abbs',
        [],
    )
    reviewed_abbs = prepare_abbreviation_table_entries(
        request.session.get('doc_abbs', []),
        initial_abbreviations=initial_abbs,
        sort_mode=table_settings['sort_mode'],
        script_order=table_settings['script_order'],
        use_correct_form=table_settings['use_correct_form'],
        scope='all',
    )

    if not reviewed_abbs and not initial_abbs:
        return render(request, 'partials/differences_section.html')
    if not reviewed_abbs:
        return render(
            request,
            'partials/differences_section.html',
            {'missing_abbs': initial_abbs},
        )
    if not initial_abbs:
        return render(
            request,
            'partials/differences_section.html',
            {'new_found': reviewed_abbs},
        )

    changes = compare_abbreviations(
        old_abbs=initial_abbs,
        new_abbs=reviewed_abbs,
    )
    return render(
        request,
        'partials/differences_section.html',
        {
            'missing_abbs': changes.get('missing_abbs', []),
            'new_found': changes.get('new_found', []),
        },
    )


@require_http_methods(['POST'])
def update_abbreviation(request: HttpRequest) -> JsonResponse:
    try:
        data = parse_request_json(request)
        abbreviation = data.get('abbreviation')
        if not abbreviation:
            raise ValueError('Abbreviation is required')

        doc_abbs: List[Abbreviation] = request.session.get('doc_abbs', [])
        update_abbreviation_selection(
            doc_abbs=doc_abbs,
            abbreviation=abbreviation,
            description=data.get('description'),
            action=data.get('action'),
        )
    except ValueError as exc:
        return JsonResponse(
            {'success': False, 'error': str(exc)},
            status=400,
        )

    request.session['doc_abbs'] = doc_abbs
    return JsonResponse({'success': True})


@require_http_methods(['POST'])
def update_workflow_state(request: HttpRequest) -> JsonResponse:
    try:
        data = parse_request_json(request)
        tool_id = data.get('tool_id')
        is_open = data.get('open')
        height = data.get('height')
        if tool_id not in WORKFLOW_TOOL_IDS:
            raise ValueError('Unknown workflow tool')
        if not isinstance(is_open, bool):
            raise ValueError('Boolean open value required')
        if height is not None:
            if isinstance(height, bool) or not isinstance(height, (int, float)):
                raise ValueError('Numeric height value required')
            if not 110 <= height <= 2000:
                raise ValueError('Workflow height is out of range')
            height = round(height)
    except ValueError as exc:
        return JsonResponse(
            {'success': False, 'error': str(exc)},
            status=400,
        )

    state = request.session.get(WORKFLOW_STATE_SESSION_KEY, {})
    tool_state = state.get(tool_id, {})
    if not isinstance(tool_state, dict):
        tool_state = {'open': bool(tool_state)}
    tool_state['open'] = is_open
    if height is not None:
        tool_state['height'] = height
    state[tool_id] = tool_state
    request.session[WORKFLOW_STATE_SESSION_KEY] = state
    return JsonResponse({'success': True})


@require_http_methods(['POST'])
def update_table_check(request: HttpRequest) -> JsonResponse:
    try:
        enabled = parse_request_json(request).get('enabled')
        if not isinstance(enabled, bool):
            raise ValueError('Boolean enabled value required')
    except ValueError as exc:
        return JsonResponse(
            {'success': False, 'error': str(exc)},
            status=400,
        )

    request.session[TABLE_CHECK_SESSION_KEY] = enabled
    return JsonResponse({'success': True})


def process_and_display(
    request: HttpRequest,
    is_demo: bool = False,
) -> HttpResponse:
    file_name = request.session.get(SESSION_FILE_KEY)
    if not file_name:
        return render(
            request,
            'upload.html',
            upload_page_context(
                error='Пожалуйста, загрузите новый файл.'
            ),
        )

    refresh_document_session(request)

    if (
        request.session.get(PROCESSED_FILE_SESSION_KEY) == file_name
        and 'doc_abbs' in request.session
        and 'initial_abbs' in request.session
    ):
        doc_abbs = request.session['doc_abbs']
        initial_abbs = request.session['initial_abbs']
    else:
        file_path = FileSystemStorage().path(file_name)
        processed = process_document(file_path)
        doc_abbs = processed.abbreviations
        initial_abbs = processed.initial_abbreviations

        request.session['doc_abbs'] = doc_abbs
        request.session['initial_abbs'] = initial_abbs
        request.session[PROCESSED_FILE_SESSION_KEY] = file_name

    table_check_enabled = (
        is_demo or request.session.get(TABLE_CHECK_SESSION_KEY) is True
    )
    show_table_check_dialog = (
        not is_demo
        and bool(initial_abbs)
        and TABLE_CHECK_SESSION_KEY not in request.session
    )
    workflow_state = request.session.get(WORKFLOW_STATE_SESSION_KEY, {})
    comparison_state = workflow_state.get('comparison-block', {})
    table_preview_state = workflow_state.get('table-preview-tool', {})
    if not isinstance(comparison_state, dict):
        comparison_state = {'open': bool(comparison_state)}
    if not isinstance(table_preview_state, dict):
        table_preview_state = {'open': bool(table_preview_state)}

    return render(
        request,
        'content.html',
        {
            'doc_abbs': doc_abbs,
            'has_initial_abbs': bool(initial_abbs),
            'initial_abbs_count': len(initial_abbs),
            'is_demo': is_demo,
            'table_check_enabled': table_check_enabled,
            'show_table_check_dialog': show_table_check_dialog,
            'comparison_open': bool(comparison_state.get('open', False)),
            'comparison_height': comparison_state.get('height'),
            'table_preview_open': bool(
                table_preview_state.get('open', False)
            ),
            'table_preview_height': table_preview_state.get('height'),
            'llm_model': settings.GIGACHAT_MODEL,
            'document_session_timeout_ms': (
                settings.DOCUMENT_SESSION_TIMEOUT_SECONDS * 1000
            ),
        },
    )


@require_http_methods(['POST'])
def preview_abbreviation_table(request: HttpRequest) -> JsonResponse:
    try:
        table_settings = parse_table_settings(
            parse_optional_json_body(request)
        )
    except ValueError as exc:
        return JsonResponse(
            {'success': False, 'error': str(exc)},
            status=400,
        )

    entries = prepare_abbreviation_table_entries(
        request.session.get('doc_abbs', []),
        initial_abbreviations=request.session.get('initial_abbs', []),
        **table_settings,
    )
    return JsonResponse({'success': True, 'entries': entries})


@require_http_methods(['POST'])
def make_abbreviation_table(request: HttpRequest) -> HttpResponse:
    try:
        table_settings = parse_table_settings(
            parse_optional_json_body(request)
        )
        entries = prepare_abbreviation_table_entries(
            request.session.get('doc_abbs', []),
            initial_abbreviations=request.session.get('initial_abbs', []),
            **table_settings,
        )
        if not entries:
            return JsonResponse(
                {
                    'success': False,
                    'error': 'Нет аббревиатур для генерации таблицы',
                },
                status=400,
            )

        content = build_abbreviation_table_docx(entries)
        response = HttpResponse(
            content,
            content_type=(
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            ),
        )
        response['Content-Disposition'] = (
            'attachment; filename=abbreviation_table.docx'
        )
        return response
    except ValueError as exc:
        return JsonResponse(
            {'success': False, 'error': str(exc)},
            status=400,
        )
    except Exception:
        logger.exception('Failed to generate abbreviation table')
        return JsonResponse(
            {'success': False, 'error': 'Не удалось сгенерировать таблицу.'},
            status=500,
        )


@require_http_methods(['GET'])
def dictionary_view(request: HttpRequest) -> HttpResponse:
    """Public read-only view of the approved abbreviation dictionary."""
    queryset = AbbreviationEntry.objects.filter(
        status='approved'
    ).order_by('abbreviation')
    validator = CharacterValidator()
    abbreviations = [
        {
            'abbreviation': entry.abbreviation,
            'description': entry.description,
            'updated_at': entry.updated_at,
            'homoglyph_parts': validator.homoglyph_parts(entry.abbreviation),
        }
        for entry in queryset
    ]

    total_count = queryset.count()
    last_month = now() - timedelta(days=30)
    new_count = queryset.filter(created_at__gte=last_month).count()
    last_entry = queryset.order_by('-updated_at').first()
    last_update = last_entry.updated_at if last_entry else None

    return render(
        request,
        'dictionary.html',
        {
            'abbreviations': abbreviations,
            'total_count': total_count,
            'new_count': new_count,
            'last_update': last_update,
        },
    )


@require_http_methods(['POST'])
def generate_description(request: HttpRequest) -> JsonResponse:
    """Generate an abbreviation description using its session contexts."""
    try:
        data = parse_request_json(request)
    except ValueError as exc:
        return JsonResponse(
            {'success': False, 'error': str(exc)},
            status=400,
        )

    unexpected_fields = set(data) - {
        'abbreviation', 'confirmed', 'context_limit', 'context_chars'
    }
    if unexpected_fields:
        return JsonResponse(
            {
                'success': False,
                'error': 'Unexpected request fields',
            },
            status=400,
        )

    abbreviation = data.get('abbreviation')
    if not abbreviation:
        return JsonResponse(
            {
                'success': False,
                'error': 'Abbreviation is required',
            },
            status=400,
        )

    if data.get('confirmed') is not True:
        return JsonResponse(
            {
                'success': False,
                'error': 'AI generation must be confirmed',
            },
            status=400,
        )

    doc_abbs: List[Abbreviation] = request.session.get('doc_abbs', [])
    entry = next(
        (
            item for item in doc_abbs
            if item.get('abbreviation') == abbreviation
        ),
        None,
    )
    if entry is None:
        return JsonResponse(
            {
                'success': False,
                'error': 'Abbreviation not found',
            },
            status=400,
        )

    contexts = entry.get('contexts', [])
    if (
        not isinstance(contexts, list)
        or not contexts
        or not all(isinstance(context, str) for context in contexts)
    ):
        return JsonResponse(
            {
                'success': False,
                'error': 'Для этого сокращения нет контекста.',
            },
            status=400,
        )

    try:
        context_limit = parse_context_limit(data.get('context_limit'))
        context_window = parse_context_window(data.get('context_chars'))
    except ValueError as exc:
        return JsonResponse(
            {'success': False, 'error': str(exc)},
            status=400,
        )

    selected_contexts = (
        contexts if context_limit is None else contexts[:context_limit]
    )
    llm_contexts = [
        trim_context(context, abbreviation, context_window)
        for context in selected_contexts
    ]

    try:
        description = generate_abbreviation_description(
            abbreviation=abbreviation,
            contexts=llm_contexts,
        )
    except LLMServiceError:
        logger.exception('Failed to generate AI description')
        return JsonResponse(
            {
                'success': False,
                'error': 'Сервис AI временно недоступен.',
            },
            status=503,
        )

    return JsonResponse(
        {
            'success': True,
            'description': description,
        }
    )
