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
from pandas import DataFrame
from collections import Counter

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

validator = CharacterValidator()

def generate_session_id(file: UploadedFile) -> str:
    """Generate unique session ID based on file name and timestamp"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    content = f"{file.name}{timestamp}".encode()
    return hashlib.md5(content).hexdigest()[:12]

def cleanup_old_files(max_age_hours: int = 0) -> None:
    """Remove old files from media directory"""
    fs = FileSystemStorage()
    now = datetime.now()
    
    for filename in fs.listdir('')[1]:
        file_path = fs.path(filename)
        file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        if now - file_modified > timedelta(hours=max_age_hours):
            fs.delete(filename)

def upload_file(request: HttpRequest) -> HttpResponse:
    cleanup_old_files()
    
    if request.method == 'POST':
        try:
            uploaded_file = request.FILES['uploaded_file']
            fs = FileSystemStorage()
            
            session_id = generate_session_id(uploaded_file)
            file_extension = os.path.splitext(uploaded_file.name)[1]
            filename = fs.save(f"{session_id}{file_extension}", uploaded_file)
            
            request.session['uploaded_file_path'] = filename
            
            return redirect('process_file_with_session', session_id=session_id)
        except KeyError:
            return render(request, 'upload.html', {'error': 'Файл не выбран'})
    
    return render(request, 'upload.html')

@require_http_methods(["POST"])
def move_to_unmatched(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body)
    abb = data['abbreviation']
    
    mixed_chars_abbs = request.session.get('mixed_chars_abbs', [])
    unmatched_abbs = request.session.get('unmatched_abbs', [])
    text = request.session.get('document_text', '')
    
    for item in mixed_chars_abbs:
        if item['original'] == abb:
            mixed_chars_abbs.remove(item)
            contexts = find_abbreviation_context(text, abb, find_all=True) if text else []
            unmatched_abbs.append({
                'abbreviation': abb,
                'contexts': contexts
            })
            break
        
    request.session['mixed_chars_abbs'] = mixed_chars_abbs
    request.session['unmatched_abbs'] = unmatched_abbs
    
    print("\n\n[move_to_unmatched]: unmatched abbs in Session: after",
          request.session.get('unmatched_abbs', []))
    
    return JsonResponse({
        'success': True,
        'mixed_chars_empty': len(mixed_chars_abbs) == 0,
        'unmatched_abbs': unmatched_abbs
    })

@require_http_methods(["POST"])
def update_abbreviation(request: HttpRequest) -> JsonResponse:
    try:
        data: Dict[str, Any] = json.loads(request.body)
        abb: Optional[str] = data.get('abbreviation')
        description: Optional[str] = data.get('description')
        action: str = data.get('action', 'add')

        matched_abbs: List[Dict[str, str]] = request.session.get('matched_abbs', [])
        
        if action == 'skip':
            matched_abbs = [item for item in matched_abbs if item['abbreviation'] != abb]
        elif action == 'edit':
            for item in matched_abbs:
                if item['abbreviation'] == abb:
                    item['description'] = description
                    break
        else:  # action == 'add'
            matched_abbs.append({'abbreviation': abb, 'description': description})
            
            # Remove from mixed_chars_abbs if found
            mixed_chars_abbs = request.session.get('mixed_chars_abbs', [])
            print( "\n\n[update_abbreviation] mixed_chars_abbs before update", mixed_chars_abbs)
            mixed_chars_abbs = [item for item in mixed_chars_abbs if item['original'] != abb]
            print( "\n\n[update_abbreviation] mixed_chars_abbs after update", mixed_chars_abbs)
            request.session['mixed_chars_abbs'] = mixed_chars_abbs
        
        request.session['matched_abbs'] = matched_abbs     

        return JsonResponse({
            'success': True, 
            'mixed_chars_empty': len(mixed_chars_abbs) == 0,
            'mixed_chars_abbs': mixed_chars_abbs,
            'unmatched_abbs': request.session.get('unmatched_abbs', [])
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

@require_http_methods(["POST"])
def update_difference_section(request: HttpRequest) -> HttpResponse:
    initial_abbs = pd.DataFrame(request.session.get('initial_abbs', []))
    matched_abbs = pd.DataFrame(request.session.get('matched_abbs', []))
    
    # Compare with initial abbreviations
    changes = compare_abbreviations(old_abbs=initial_abbs, new_abbs=matched_abbs)
    
    return render(request, 'partials/differences_section.html', {
        'missing_abbs': changes.get('missing_abbs', pd.DataFrame()).to_dict('records'),
        'new_found_abbs': changes.get('new_found', pd.DataFrame()).to_dict('records'),
    })

def process_and_display(request: HttpRequest, session_id: Optional[str] = None) -> HttpResponse:
    # Get file path
    filename = request.session.get('uploaded_file_path')
    if not filename:
        return render(request, 'upload.html', 
                     {'error': 'Файл не найден. Пожалуйста, загрузите новый файл.'})

    fs = FileSystemStorage()
    file_path = fs.path(filename)

    # Process document
    initial_abbs: DataFrame = get_init_abb_table(file_path)
    doc = Document(file_path)
    text: str = extract_relevant_text(doc)
    doc_abbs: Counter[str] = extract_abbs_from_text(text)
    
    # Load dictionary and prepare collections
    abb_dict: DataFrame = load_abbreviation_dict()
    mixed_chars_abbs: List[Dict[str, Any]] = []
    remaining_abbs: Counter[str] = Counter()
    
    # Check for mixed characters only for new abbreviations
    dict_abbs: set = set(abb_dict['abbreviation'])
    for abb, count in doc_abbs.items():
        if abb in dict_abbs:
            remaining_abbs[abb] += count
            continue
            
        validation_result = validator.validate_abbreviation(abb, abb_dict)
        print( "\n\n[process_and_display:validator] validation_result", validation_result)
        if validation_result['is_mixed'] and validation_result['matches']:
            mixed_chars_abbs.append(validation_result)
        else:
            remaining_abbs[abb] += count

    # Separate pending abbreviations into matched and new
    matched_abbs, unmatched_abbs = separate_abbs(remaining_abbs, abb_dict, text)
    
    # Store variables in session
    request.session['document_text'] = text
    request.session['mixed_chars_abbs'] = mixed_chars_abbs
    request.session['unmatched_abbs'] = unmatched_abbs
    request.session['matched_abbs'] = matched_abbs.to_dict('records')
    
    print( "\n\n[process_and_display] initial mixed_chars_abbs", 
           request.session['mixed_chars_abbs'])
    
    # Compare with initial abbreviations
    changes = compare_abbreviations(old_abbs=initial_abbs, new_abbs=matched_abbs)
    
    return render(request, 'content.html', {
        'missing_abbs': changes.get('missing_abbs', pd.DataFrame()).to_dict('records'),
        'new_found_abbs': changes.get('new_found', pd.DataFrame()).to_dict('records'),
        'mixed_chars_abbs': mixed_chars_abbs,
        'unmatched_abbs': unmatched_abbs,
        'show_unmatched': False
    })

@require_http_methods(["POST"])
def make_abbreviation_table(request: HttpRequest) -> JsonResponse:
    try:
        matched_abbs = pd.DataFrame(request.session.get('matched_abbs', []))
        if matched_abbs.empty:
            return JsonResponse({
                'success': False, 
                'error': 'Нет аббревиатур для генерации таблицы'
            })

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
        print(f"[ERROR] Failed to generate table: {str(e)}")
        print(traceback.format_exc())
        
        return JsonResponse({
            'success': False, 
            'error': 'Ошибка при генерации таблицы'
        })