import io
import os
import json
import hashlib
import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import UploadedFile
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from docx import Document
from typing import Dict, List, Union, Any
from datetime import datetime, timedelta

from .utils import (
    Abbreviation,
    load_abbreviation_dict,
    AbbreviationTableExtractor,
    process_abbreviations,
    AbbreviationFormatter,
    compare_abbreviations,
    AbbreviationTableGenerator
)

DEMO_SESSION_ID = 'test_drive'

extractor = AbbreviationTableExtractor()
formatter = AbbreviationFormatter()
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

def cleanup_old_files(exclude_id: str, max_hours: int = 0) -> None:
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
            logger.info(f"Uploading file: {uploaded_file.name},"
                        f" size: {uploaded_file.size} bytes")

            fs = FileSystemStorage()            
            session_id = generate_session_id(uploaded_file)
            file_extension = os.path.splitext(uploaded_file.name)[1]
            filename = fs.save(f"{session_id}{file_extension}", uploaded_file)
            
            request.session['uploaded_file_path'] = filename
            
            # Check if it's an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'session_id': session_id})
            
            return render(request, 'upload.html', {
                'session_id': session_id,
                'demo_session_id': DEMO_SESSION_ID
            })
        except KeyError:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'File not selected'}, status=400)
            return render(request, 'upload.html', {
                'error': 'File not selected',
                'demo_session_id': DEMO_SESSION_ID
            })
    
    # For GET request
    request.session.flush()
    session_id = request.session.get(
        'uploaded_file_path', ''
        ).split('.')[0] if request.session.get(
            'uploaded_file_path'
            ) else None
    return render(request, 'upload.html', {
        'session_id': session_id,
        'demo_session_id': DEMO_SESSION_ID
    })

@require_http_methods(["GET"])
def process_file_with_session(
        request: HttpRequest,
        session_id: str
    ) -> HttpResponse:
    fs = FileSystemStorage()

    for filename in fs.listdir('')[1]:
        if filename.startswith(session_id):
            print(f"Found file: {filename}")
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

def get_processed_doc_abbs(request: HttpRequest) -> List[Dict[str, Any]]:
    """
    Extract and abbreviations with user-selected descriptions from session.
    """
    doc_abbs = request.session.get('doc_abbs', [])    
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
    initial_abbs: List[Abbreviation] = request.session.get('initial_abbs', [])

    # Compare abbs with descriptions with initial abbreviations
    processed_doc_abbs = get_processed_doc_abbs(request)
    
    if not processed_doc_abbs and not initial_abbs:
        logger.debug(f"Both processed doc abbs and initial abbs are empty")
        return render(request, 'partials/differences_section.html')
    
    if not processed_doc_abbs:
        logger.debug(f"Processed doc abbs is empty")
        return render(request, 'partials/differences_section.html', {
            'missing_abbs': initial_abbs
        })
    
    if not initial_abbs:
        logger.debug(f"Initial abbs is empty")
        return render(request, 'partials/differences_section.html', {
            'new_found': processed_doc_abbs
        })

    changes = compare_abbreviations(
        old_abbs=initial_abbs,
        new_abbs=processed_doc_abbs
    )

    return render(request, 'partials/differences_section.html', {
        'missing_abbs': changes.get('missing_abbs', []),
        'new_found': changes.get('new_found', []),
    })

def update_abbreviation(request: HttpRequest) -> JsonResponse:
    data = parse_request_json(request)
    
    abb = data.get('abbreviation')
    description = data.get('description')
    action = data.get('action')

    doc_abbs: List[Abbreviation] = request.session.get('doc_abbs', [])
    abb_entry = next(
        (entry for entry in doc_abbs if entry['abbreviation'] == abb), None
    )

    if action == 'add':
        abb_entry['selected_description'] = description

    elif action == 'skip':
        abb_entry['selected_description'] = None

    request.session['doc_abbs'] = doc_abbs
    return JsonResponse({'success': True})
    

def process_and_display(request: HttpRequest) -> HttpResponse:
    logger.debug(f"process_and_display function called")
    logger.debug(f"Session ID: {request.session.session_key}")
    logger.debug("Session data lengths before clearing: %s", {
        key: len(value) if hasattr(value, '__len__') else 'Not measurable'
        for key, value in request.session.items()
    })
    
    # Get file
    file_path = request.session.get('uploaded_file_path')
    if not file_path:
        return render(request, 'upload.html', 
                     {'error': 'Пожалуйста, загрузите новый файл.'})
    
    # Clear session but keep the file path
    request.session.clear()
    request.session['uploaded_file_path'] = file_path
    
    # Get full path to file
    file_path = FileSystemStorage().path(file_path)
    logger.debug(f"Processing file: {file_path}")

    # Load dictionary
    abb_dict = load_abbreviation_dict()
    logger.debug(
        "Loaded abbreviation dictionary:"
        f"{len(abb_dict)}"
    )
    
    # Extract initial table with abbreviations from document
    doc = Document(file_path)
    initial_abbs = extractor.get_abbreviation_table(doc)
    logger.debug(f"Loaded initial abbreviations: {len(initial_abbs)}")
    
    # Process abbreviations
    doc_abbs: List[Abbreviation] = process_abbreviations(doc, abb_dict)
    
    # Store variables in session
    request.session['doc_abbs'] = doc_abbs
    request.session['initial_abbs'] = initial_abbs
    
    return render(request, 'content.html', {
        'doc_abbs': doc_abbs
    })

@require_http_methods(["POST"])
def make_abbreviation_table(
    request: HttpRequest
    ) -> Union[HttpResponse, JsonResponse]:
    logger.debug(f"make_abbreviation_table function called")
    try:
        processed_doc_abbs = get_processed_doc_abbs(request)
        
        if not processed_doc_abbs:
            return JsonResponse({
                'success': False, 
                'error': 'Нет аббревиатур для генерации таблицы'
            }, status=400)

        processed_doc_abbs = formatter.clean_and_sort_abbreviations(
            processed_doc_abbs
        )
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