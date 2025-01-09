import io
import os
import json
import traceback
import pandas as pd
from collections import Counter
from docx import Document
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.template.loader import render_to_string
import hashlib
from datetime import datetime, timedelta
from django.views.decorators.http import require_http_methods
from typing import Dict, List, Optional, Union, Any
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.core.files.uploadedfile import UploadedFile
from django.contrib import messages
from pandas import DataFrame
from collections import Counter
import logging
from django.core.files.base import ContentFile
from django.conf import settings

from .utils import (
    extract_relevant_text,
    extract_abbs_from_text,
    separate_abbs,
    get_init_abb_table,
    load_abbreviation_dict,
    compare_abbreviations,
    generate_abbreviation_table,
    CharacterValidator,
    find_abbreviation_context
)

DEMO_SESSION_ID = 'test_drive'

validator = CharacterValidator()
logger = logging.getLogger('abb_app')

if not logger.hasHandlers():
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)

def generate_session_id(file: UploadedFile) -> str:
    """Generate unique session ID based on file name and timestamp"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    content = f"{file.name}{timestamp}".encode()
    return hashlib.md5(content).hexdigest()[:12]

def cleanup_old_files(max_age_hours: int = 1, exclude_session_id: str = None) -> None:
    """Remove old files from media directory"""
    fs = FileSystemStorage()
    now = datetime.now()
    
    for filename in fs.listdir('')[1]:
        # Skip demo file
        if exclude_session_id and filename.startswith(exclude_session_id):
            continue
            
        file_path = fs.path(filename)
        file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        if now - file_modified > timedelta(hours=max_age_hours):
            fs.delete(filename)

@require_http_methods(["GET", "POST"])
def upload_file(request: HttpRequest) -> HttpResponse:
    """Generate unique session ID based on file name and timestamp"""
    if request.method == 'POST':
        cleanup_old_files(exclude_session_id=DEMO_SESSION_ID)
        
        try:
            uploaded_file = request.FILES['uploaded_file']
            logger.info(f"Uploading file: {uploaded_file.name}, size: {uploaded_file.size} bytes")
            
            if uploaded_file.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
                return render(request, 'upload.html', {
                    'error': f'Файл слишком большой. Максимальный размер: {settings.FILE_UPLOAD_MAX_MEMORY_SIZE/1048576:.1f}MB',
                    'demo_session_id': DEMO_SESSION_ID
                })

            fs = FileSystemStorage()
            
            session_id = generate_session_id(uploaded_file)
            file_extension = os.path.splitext(uploaded_file.name)[1]
            filename = fs.save(f"{session_id}{file_extension}", uploaded_file)
            
            request.session['uploaded_file_path'] = filename
            
            return render(request, 'upload.html', {
                'session_id': session_id,
                'demo_session_id': DEMO_SESSION_ID
            })
        except KeyError:
            return render(request, 'upload.html', {
                'error': 'File not selected',
                'demo_session_id': DEMO_SESSION_ID
            })
    
    # For GET request
    session_id = request.session.get('uploaded_file_path', '').split('.')[0] if request.session.get('uploaded_file_path') else None
    return render(request, 'upload.html', {
        'session_id': session_id,
        'demo_session_id': DEMO_SESSION_ID  # Always pass demo_session_id
    })

@require_http_methods(["GET"])
def process_file_with_session(request: HttpRequest, session_id: str) -> HttpResponse:
    fs = FileSystemStorage()
    
    for filename in fs.listdir('')[1]:
        if filename.startswith(session_id):
            request.session['uploaded_file_path'] = filename
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success'})
            return process_and_display(request)
    
    # If file not found for this session_id
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'error'}, status=404)
    messages.error(request, 'Сессия не найдена или истекла')
    return redirect('upload_file')

def parse_request_json(request: HttpRequest) -> Dict[str, Any]:
    data: Dict[str, Any] = json.loads(request.body)
    if not data:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    return data

@require_http_methods(["POST"])
def get_unmatched_template(request: HttpRequest) -> HttpResponse:
    data = parse_request_json(request)
    unmatched_abbs = data.get('unmatched_abbs', [])         
    
    html = render_to_string('partials/unmatched_section.html', {
        'unmatched_abbs': unmatched_abbs
    })
    return HttpResponse(html)

def get_session_data(
        request: HttpRequest,
        keys: Union[str, List[str]],
        default: Optional[Any] = []
        ) -> Union[Any, Dict[str, Any]]:
    """
    Get data from session by one or several keys.
    """
    if isinstance(keys, list):
        return {key: request.session.get(key, default) for key in keys}
    return request.session.get(keys, default)


def set_session_data(
        request: HttpRequest,
        data: Dict[str, Any]
        ) -> None:
    """
    Set several values in session at once.
    """
    for key, value in data.items():
        request.session[key] = value

@require_http_methods(["POST"])
def move_to_unmatched(request: HttpRequest) -> JsonResponse:
    data = parse_request_json(request)
    abb = data['abbreviation']

    session_data = get_session_data(request, [
        'matched_abbs',
        'unmatched_abbs',
        'multi_desc_abbs',
        'mixed_chars_abbs',
        'document_text'
    ])

    mixed_chars_abbs = session_data['mixed_chars_abbs']
    multi_desc_abbs = session_data['multi_desc_abbs']
    unmatched_abbs = session_data['unmatched_abbs']
    text = session_data['document_text']
    
    for item in mixed_chars_abbs:
        if item['original'] == abb:
            mixed_chars_abbs.remove(item)
            contexts = find_abbreviation_context(text, abb, find_all=True) if text else []
            unmatched_abbs.append({
                'abbreviation': abb,
                'contexts': contexts
            })
            break

    for item in multi_desc_abbs:
        if item['abbreviation'] == abb:
            multi_desc_abbs.remove(item)
            contexts = find_abbreviation_context(text, abb, find_all=True) if text else []
            unmatched_abbs.append({
                'abbreviation': abb,
                'contexts': contexts
            })
            break
    
    set_session_data(request, {
        'mixed_chars_abbs': mixed_chars_abbs,
        'unmatched_abbs': unmatched_abbs
    })
    
    logger.debug(
        "\nmove_to_unmatched - Stats after operation:\nunmatched_abbs=%d,\nmixed_chars_abbs=%d,\nmulti_desc_abbs=%d\n",
        len(unmatched_abbs),
        len(mixed_chars_abbs),
        len(multi_desc_abbs)
    )
    
    return JsonResponse({
        'success': True,
        'mixed_chars_empty': len(mixed_chars_abbs) == 0,
        'multi_desc_empty': len(multi_desc_abbs) == 0,
        'unmatched_abbs': unmatched_abbs        
    })

@require_http_methods(["POST"])
def update_abbreviation(request: HttpRequest) -> JsonResponse:
    data = parse_request_json(request)
    abb = data.get('abbreviation')
    orig_form = data.get('orig_form')
    description = data.get('description')
    action = data.get('action', 'add')

    session_data = get_session_data(request, [
        'matched_abbs',
        'unmatched_abbs',
        'multi_desc_abbs',
        'mixed_chars_abbs'
    ])

    matched_abbs = session_data['matched_abbs']
    unmatched_abbs = session_data['unmatched_abbs']
    mixed_chars_abbs = session_data['mixed_chars_abbs']
    multi_desc_abbs = session_data['multi_desc_abbs']
    
    if action == 'skip':
        pass
    elif action == 'edit':
        for item in matched_abbs:
            if item['abbreviation'] == abb:
                item['description'] = description
                break
    else:  # action == 'add'
        logger.debug("\nupdate_abbreviation - Adding abbreviation:\n%s with description: %s", 
                    abb, description)
        matched_abbs.append({'abbreviation': abb, 'description': description})

        # Remove from mixed_chars_abbs/multi_desc_abbs if found
        mixed_chars_abbs = [item for item in mixed_chars_abbs if item['original'] != orig_form]
        multi_desc_abbs = [item for item in multi_desc_abbs if item['abbreviation'] != abb]
        
        set_session_data(request, {
            'mixed_chars_abbs': mixed_chars_abbs,
            'multi_desc_abbs': multi_desc_abbs
        })

    logger.debug(
        "\nupdate_abbreviation - Stats:\nmatched_abbs=%d,\nunmatched_abbs=%d,\nmixed_chars_abbs=%d,\nmulti_desc_abbs=%d\n",
        len(matched_abbs),
        len(unmatched_abbs),
        len(mixed_chars_abbs),
        len(multi_desc_abbs)
    )
    
    set_session_data(request, {'matched_abbs': matched_abbs})

    return JsonResponse({
        'success': True, 
        'mixed_chars_empty': len(mixed_chars_abbs) == 0,
        'multi_desc_empty': len(multi_desc_abbs) == 0,
        'mixed_chars_abbs': mixed_chars_abbs,
        'unmatched_abbs': unmatched_abbs
    })

@require_http_methods(["POST"])
def update_difference_section(request: HttpRequest) -> HttpResponse:
    logger.debug(f"[update_difference_section] Session ID: {request.session.session_key}")
    logger.debug("[update_difference_section] Session data lengths: %s", {
        key: len(value) if hasattr(value, '__len__') else 'Not measurable'
        for key, value in request.session.items()
    })
    session_data = get_session_data(request, [
        'initial_abbs',
        'matched_abbs'
    ])
    initial_abbs = pd.DataFrame(session_data['initial_abbs'])
    matched_abbs = pd.DataFrame(session_data['matched_abbs'])
    
    # Compare with initial abbreviations
    changes = compare_abbreviations(old_abbs=initial_abbs, new_abbs=matched_abbs)
    
    return render(request, 'partials/differences_section.html', {
        'missing_abbs': changes.get('missing_abbs', pd.DataFrame()).to_dict('records'),
        'new_found_abbs': changes.get('new_found', pd.DataFrame()).to_dict('records'),
    })

def process_and_display(request: HttpRequest) -> HttpResponse:
    logger.debug(f"[process_and_display] Session ID: {request.session.session_key}")
    logger.debug("[process_and_display] Session data lengths: %s", {
        key: len(value) if hasattr(value, '__len__') else 'Not measurable'
        for key, value in request.session.items()
    })
    
    # Get file path before clearing session
    file_path = request.session.get('uploaded_file_path')
    if not file_path:
        return render(request, 'upload.html', 
                     {'error': 'Пожалуйста, загрузите новый файл.'})
    
    # Clear session but keep the file path
    temp_file_path = file_path
    request.session.clear()
    request.session['uploaded_file_path'] = temp_file_path
    
    # Get full path to file
    fs = FileSystemStorage()
    file_path = fs.path(file_path)
    logger.debug(f"[process_and_display] Processing file: {file_path}")

    # Process document
    initial_abbs: DataFrame = get_init_abb_table(file_path)
    logger.debug(f"[process_and_display] Loaded initial abbreviations: {len(initial_abbs)}")
    
    doc = Document(file_path)
    text: str = extract_relevant_text(doc)
    logger.debug(f"[process_and_display] Extracted {len(text)} words")
    doc_abbs: Counter[str] = extract_abbs_from_text(text)
    logger.debug(f"[process_and_display] Extracted {len(doc_abbs)} abbreviations")
    
    # Load dictionary and prepare collections
    abb_dict: DataFrame = load_abbreviation_dict()
    dict_abbs: set = set(abb_dict['abbreviation'])
    logger.debug(f"[process_and_display] Loaded abbreviation dictionary: {len(dict_abbs)}")
    mixed_chars_abbs: List[Dict[str, Any]] = []
    multi_desc_abbs: List[Dict[str, Any]] = []
    remaining_abbs: Counter[str] = Counter()
    
    # Sort to multi_desc_abbs and remaining_abbs
    logger.debug(f"[process_and_display] starting sorting")
    for abb, count in doc_abbs.items():
        if abb in dict_abbs:
            # save abb and descriptions to multi_desc_abbs
            if len(abb_dict[abb_dict['abbreviation'] == abb]) > 1:
                multi_desc_abbs.append({
                    'abbreviation': abb,
                    'descriptions': abb_dict[
                        abb_dict['abbreviation'] == abb
                    ]['description'].tolist()
                })
            else:
                remaining_abbs[abb] += count
            continue
        
        # Check for mixed characters only for new abbreviations if char len is less than 10
        if len(abb) >= 10:
            remaining_abbs[abb] += count
            continue
            
        validation_result = validator.validate_abbreviation(abb, abb_dict)
        if validation_result.get('correct_form'):
            mixed_chars_abbs.append(validation_result)
            logger.debug(f"[process_and_display] mixed characters found for {abb}")
        else:
            remaining_abbs[abb] += count

    # Separate pending abbreviations into matched and new
    matched_abbs, unmatched_abbs = separate_abbs(remaining_abbs, abb_dict, text)
    
    logger.debug(f"[process_and_display] Abbreviations sorted")
    
    # Store variables in session
    set_session_data(request, {
        'document_text': text,
        'mixed_chars_abbs': mixed_chars_abbs,
        'unmatched_abbs': unmatched_abbs,
        'multi_desc_abbs': multi_desc_abbs,
        'matched_abbs': matched_abbs.to_dict('records'),
        'initial_abbs': initial_abbs.to_dict('records')
    })
    
    # Compare with initial abbreviations
    changes = compare_abbreviations(old_abbs=initial_abbs, new_abbs=matched_abbs)
    
    return render(request, 'content.html', {
        'missing_abbs': changes.get('missing_abbs', pd.DataFrame()).to_dict('records'),
        'new_found_abbs': changes.get('new_found', pd.DataFrame()).to_dict('records'),
        'mixed_chars_abbs': mixed_chars_abbs,
        'multi_desc_abbs': multi_desc_abbs,
        'unmatched_abbs': unmatched_abbs,
        'show_unmatched': False
    })

@require_http_methods(["POST"])
def make_abbreviation_table(
    request: HttpRequest
    ) -> Union[HttpResponse, JsonResponse]:
    try:
        matched_abbs = pd.DataFrame(get_session_data(request, 'matched_abbs'))
        if matched_abbs.empty:
            return JsonResponse({
                'success': False, 
                'error': 'Нет аббревиатур для генерации таблицы'
            }, status=400)

        file_stream = io.BytesIO()
        doc = generate_abbreviation_table(matched_abbs)
        doc.save(file_stream)
        file_stream.seek(0)
        
        response = HttpResponse(
            file_stream.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = 'attachment; filename=abbreviation_table.docx'
        return response
    
    except Exception as e:
        logger.error("Failed to generate table: %s", str(e))
        logger.error("Traceback: %s", traceback.format_exc())
        
        return JsonResponse({
            'success': False, 
            'error': 'Ошибка при генерации таблицы'
        }, status=500)