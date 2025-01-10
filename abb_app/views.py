import io
import os
import json
import traceback
import hashlib
import logging

from docx import Document

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import UploadedFile
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.conf import settings

from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta

from .utils import (
    load_abbreviation_dict,
    AbbreviationTableExtractor,
    TextProcessor,
    process_abbreviations,
    AbbreviationFormatter,
    CharacterValidator,
    compare_abbreviations,
    AbbreviationTableGenerator
)

DEMO_SESSION_ID = 'test_drive'

extractor = AbbreviationTableExtractor()
text_processor = TextProcessor()
formatter = AbbreviationFormatter()
validator = CharacterValidator()
generator = AbbreviationTableGenerator()
logger = logging.getLogger('abb_app')


if not logger.hasHandlers():
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)

def generate_session_id(file: UploadedFile) -> str:
    """Generate unique session ID based on file name and timestamp"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    content = f"{file.name}{timestamp}".encode()
    return hashlib.md5(content).hexdigest()[:12]

def cleanup_old_files(exclude_id: str, max_hours: int = 1) -> None:
    """Remove old files from media directory"""
    fs = FileSystemStorage()
    now = datetime.now()
    
    for filename in fs.listdir('')[1]:
        if filename.startswith(exclude_id):
            continue
            
        file_path = fs.path(filename)
        file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        if now - file_modified > timedelta(hours=max_hours):
            fs.delete(filename)

@require_http_methods(["GET", "POST"])
def upload_file(request: HttpRequest) -> HttpResponse:
    """Generate unique session ID based on file name and timestamp"""
    if request.method == 'POST':
        cleanup_old_files(exclude_id=DEMO_SESSION_ID)
        
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
def process_file_with_session(
        request: HttpRequest,
        session_id: str
    ) -> HttpResponse:
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

def get_processed_doc_abbs(request: HttpRequest) -> List[Dict[str, Any]]:
    """
    Extract and process abbreviations with selected descriptions from session.
    """
    session_data = get_session_data(request, ['doc_abbs'])
    doc_abbs = session_data.get('doc_abbs', [])
    
    processed_doc_abbs = [
        {
            'abbreviation': abb['abbreviation'],
            'description': abb['selected_description']
        }
        for abb in doc_abbs
        if abb.get('selected_description') is not None
    ]
    
    return processed_doc_abbs

@require_http_methods(["POST"])
def update_difference_section(request: HttpRequest) -> HttpResponse:
    session_data = get_session_data(request, [
        'initial_abbs'
    ])
    initial_abbs = session_data['initial_abbs']

    # Compare abbs with descriptions with initial abbreviations
    processed_doc_abbs = get_processed_doc_abbs(request)
    
    # if processed_doc_abbs is empty, return only initial_abbs
    if not processed_doc_abbs:
        return render(request, 'partials/differences_section.html', {
            'missing_abbs': initial_abbs
        })

    changes = compare_abbreviations(old_abbs=initial_abbs, new_abbs=processed_doc_abbs)
    
    return render(request, 'partials/differences_section.html', {
        'missing_abbs': changes.get('missing_abbs', []),
        'new_found': changes.get('new_found', []),
    })

def process_and_display(request: HttpRequest) -> HttpResponse:
    logger.debug(f"[process_and_display] Session ID: {request.session.session_key}")
    logger.debug("[process_and_display] Session data lengths: %s", {
        key: len(value) if hasattr(value, '__len__') else 'Not measurable'
        for key, value in request.session.items()
    })
    
    # Get file
    file_path = request.session.get('uploaded_file_path')
    if not file_path:
        return render(request, 'upload.html', 
                     {'error': 'Пожалуйста, загрузите новый файл.'})
    
    # Clear session but keep the file path
    temp_file_path = file_path
    request.session.clear()
    request.session['uploaded_file_path'] = temp_file_path
    
    # Get full path to file
    file_path = FileSystemStorage().path(file_path)
    logger.debug(f"[process_and_display] Processing file: {file_path}")

    # Load dictionary
    abb_dict = load_abbreviation_dict()
    logger.debug(
        "[process_and_display] Loaded abbreviation dictionary:"
        f"{len(abb_dict)}"
    )
    
    # Extract initial table with abbreviations from document
    doc = Document(file_path)
    initial_abbs = extractor.get_abbreviation_table(doc)
    logger.debug(f"[process_and_display] Loaded initial abbreviations: {len(initial_abbs)}")
    
    # Process abbreviations
    doc_abbs = process_abbreviations(doc, abb_dict)
    logger.debug(f"[process_and_display] Abbreviations objects created: {len(doc_abbs)}")
    
    # Store variables in session
    set_session_data(request, {
        'doc_abbs': doc_abbs,
        'initial_abbs': initial_abbs
    })
    
    return render(request, 'content.html', {
        'doc_abbs': doc_abbs
    })

@require_http_methods(["POST"])
def make_abbreviation_table(
    request: HttpRequest
    ) -> Union[HttpResponse, JsonResponse]:
    try:
        processed_doc_abbs = get_processed_doc_abbs(request)
        if not processed_doc_abbs:
            return JsonResponse({
                'success': False, 
                'error': 'Нет аббревиатур для генерации таблицы'
            }, status=400)

        # Generate document
        file_stream = io.BytesIO()
        doc = generator.generate_document(processed_doc_abbs)
        doc.save(file_stream)
        file_stream.seek(0)
        
        response = HttpResponse(
            file_stream.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = 'attachment; filename=abbreviation_table.docx'
        return response
    
    except Exception as e:
        logger.error("Failed to generate table", exc_info=True)        
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)