import io
import os
import json
import traceback
import pandas as pd
from docx import Document
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.template.loader import render_to_string
import hashlib
from datetime import datetime, timedelta

from .utils import (
    extract_relevant_text,
    extract_abbs_from_text,
    find_abbreviation_context,
    get_init_abb_table,
    load_abbreviation_dict,
    compare_abbreviations,
    generate_abbreviation_table
)

def generate_session_id(file):
    """Generate unique session ID based on file name and timestamp"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    content = f"{file.name}{timestamp}".encode()
    return hashlib.md5(content).hexdigest()[:12]

def cleanup_old_files(max_age_hours=0):
    """
    Remove old files from media directory
    """
    fs = FileSystemStorage()
    now = datetime.now()
    files = fs.listdir('')[1]
    
    for filename in files:
        file_path = fs.path(filename)
        file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        if now - file_modified > timedelta(hours=max_age_hours):
            try:
                fs.delete(filename)
                print(f"[INFO] Deleted old file: {filename}")
            except Exception as e:
                print(f"[ERROR] Failed to delete {filename}: {str(e)}")

def upload_file(request):
    cleanup_old_files()
    
    if request.method == 'POST' and request.FILES.get('uploaded_file'):
        uploaded_file = request.FILES['uploaded_file']
        fs = FileSystemStorage()
        
        session_id = generate_session_id(uploaded_file)
        file_extension = os.path.splitext(uploaded_file.name)[1]
        filename = fs.save(f"{session_id}{file_extension}", uploaded_file)
        
        request.session['session_id'] = session_id
        request.session['uploaded_file_path'] = filename
        
        return redirect('process_file_with_session', session_id=session_id)
    return render(request, 'upload.html')

def separate_abbs(doc_abbs, abb_dict, text):
    freq_abbs = {abb: count for abb, count in doc_abbs.items() if count > 1}
    matched_abbs = abb_dict[abb_dict['abbreviation'].isin(freq_abbs)].copy()
    new_abbs = set(freq_abbs) - set(matched_abbs['abbreviation'])

    return matched_abbs, [
        {'abbreviation': abb, 'contexts': find_abbreviation_context(text, abb, find_all=True)}
        for abb in new_abbs
    ]

def update_abbreviation(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request'})

    data = json.loads(request.body)
    abb = data.get('abbreviation')
    description = data.get('description')
    action = data.get('action', 'add')

    if not abb or not description:
        return JsonResponse({'success': False, 'error': 'Invalid data'})
    
    matched_abbs = request.session.get('matched_abbs', [])
    
    if action == 'skip':
        matched_abbs = [item for item in matched_abbs if item['abbreviation'] != abb]
    elif action == 'edit':
        for item in matched_abbs:
            if item['abbreviation'] == abb:
                item['description'] = description
                break
    else:  # add
        matched_abbs.append({'abbreviation': abb, 'description': description})
    
    request.session['matched_abbs'] = matched_abbs
    return JsonResponse({'success': True})

def update_difference_section(request):
    if request.method != 'POST':
        return JsonResponse({'success': False})

    initial_abbs = pd.DataFrame(request.session.get('initial_abbs', []))
    matched_abbs = pd.DataFrame(request.session.get('matched_abbs', []))
    changes = compare_abbreviations(old_abbs=initial_abbs, new_abbs=matched_abbs)

    html = render_to_string(
        'partials/differences_section.html',
        {
            'missing_abbs': changes.get('missing_abbs', pd.DataFrame()).to_dict('records'),
            'new_found_abbs': changes.get('new_found', pd.DataFrame()).to_dict('records')
        }
    )
    return JsonResponse({'html': html})

def process_and_display(request, session_id=None):
    if session_id and session_id != request.session.get('session_id'):
        request.session['session_id'] = session_id
        
        fs = FileSystemStorage()
        files = fs.listdir('')[1]
        filename = next((f for f in files if f.startswith(session_id)), None)
        
        if filename:
            request.session['uploaded_file_path'] = filename
        else:
            return render(request, 'upload.html', {
                'error': 'Session file not found. Please upload a new file.'
            })

    filename = request.session.get('uploaded_file_path')
    if not filename:
        return render(request, 'upload.html', {
            'error': 'No file was uploaded. Please upload a file.'
        })

    fs = FileSystemStorage()
    file_path = fs.path(filename)
    
    if not os.path.exists(file_path):
        request.session.pop('uploaded_file_path', None)
        request.session.pop('session_id', None)
        return render(request, 'upload.html', {
            'error': 'The file no longer exists. Please upload a new file.'
        })

    # Process document
    initial_abbs = get_init_abb_table(file_path)
    if initial_abbs.empty:
        initial_abbs = pd.DataFrame(columns=['abbreviation', 'description'])

    doc = Document(file_path)
    text = extract_relevant_text(doc)
    doc_abbs = extract_abbs_from_text(text)
    matched_abbs, unmatched_abbs = separate_abbs(doc_abbs, load_abbreviation_dict(), text)

    request.session.update({
        'matched_abbs': matched_abbs.to_dict('records'),
        'initial_abbs': initial_abbs.to_dict('records')
    })
    
    changes = compare_abbreviations(old_abbs=initial_abbs, new_abbs=matched_abbs)
    return render(request, 'content.html', {
        'missing_abbs': changes.get('missing_abbs', pd.DataFrame()).to_dict('records'),
        'new_found_abbs': changes.get('new_found', pd.DataFrame()).to_dict('records'),
        'unmatched_abbs': unmatched_abbs
    })

def make_abbreviation_table(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не разрешен'}, status=405)
    
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
        return JsonResponse({
            'success': False, 
            'error': f'Ошибка при генерации таблицы: {str(e)}\n{traceback.format_exc()}'
        })