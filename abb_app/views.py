from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.template.loader import render_to_string
from docx import Document
from backend_scripts.process_doc import (
    load_abbreviation_dict,
    extract_relevant_text,
    extract_abbs_from_text,
    find_abbreviation_context,
    generate_all_mixed_forms,
    highlight_mixed_characters,
    compare_abbreviations,
    check_inconsistencies,
    get_custom_description_web
)
from backend_scripts.extract_abbs import (
    get_init_abb_table
)
import os
import json
import pandas as pd
from django.http import JsonResponse

def upload_file(request):
    if request.method == 'POST' and request.FILES.get('uploaded_file'):
        uploaded_file = request.FILES['uploaded_file']
        fs = FileSystemStorage()
        file_path = fs.save(uploaded_file.name, uploaded_file)        
        request.session['uploaded_file_path'] = fs.path(file_path)
        return redirect('process_file')

    return render(request, 'upload.html')

def separate_abbs(doc_abbs, abb_dict, text):
    freq_abbs = {abb: count for abb, count in doc_abbs.items() if count > 1}
    matched_abbs = abb_dict[abb_dict['abbreviation'].isin(freq_abbs)].copy()
    new_abbs = set(freq_abbs) - set(matched_abbs['abbreviation'])

    unmatched_abbs = [
        {'abbreviation': abb,
         'contexts': find_abbreviation_context(text, abb, find_all=True)} for abb in new_abbs
    ]
    return matched_abbs, unmatched_abbs

def update_abbreviation(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        abb = data.get('abbreviation')
        description = data.get('description')
        action = data.get('action', 'add')  # 'add', 'skip', или 'edit'

        if not abb or not description:
            return JsonResponse({'success': False, 'error': 'Invalid data'})
        
        # Retrieve or initialize matched_abbs from session
        matched_abbs = request.session.get('matched_abbs', [])

        if action == 'skip':
            matched_abbs = [item for item in matched_abbs 
                          if item['abbreviation'] != abb]
            
        elif action == 'edit':
            for item in matched_abbs:
                if item['abbreviation'] == abb:
                    item['description'] = description
                    break
        else:
            new_entry = {'abbreviation': abb, 'description': description}
            matched_abbs.append(new_entry)
        
        request.session['matched_abbs'] = matched_abbs

        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid request'})

def update_difference_section(request):
    if request.method == 'POST':
        initial_abbs = pd.DataFrame(request.session.get('initial_abbs', []))
        matched_abbs = pd.DataFrame(request.session.get('matched_abbs', []))

        print("DEBUG: matched_abbs loaded in update_difference_section:\n", matched_abbs, flush=True)
        print("DEBUG: initial_abbs in update_difference_section:\n", initial_abbs, flush=True)  
    
        changes = compare_abbreviations(old_abbs=initial_abbs, new_abbs=matched_abbs)
        missing_abbs = changes.get('missing_abbs', pd.DataFrame())
        new_found_abbs = changes.get('new_found', pd.DataFrame())

        html = render_to_string(
            'partials/differences_section.html',
            {
                'missing_abbs': missing_abbs.to_dict('records'),
                'new_found_abbs': new_found_abbs.to_dict('records')
            }
        )
        return JsonResponse({'html': html})

    return JsonResponse({'success': False})

def process_and_display(request):
    print("DEBUG: process_and_display triggered.", flush=True)
    file_path = request.session.get('uploaded_file_path', None)

    if not file_path or not os.path.exists(file_path):
        request.session.pop('uploaded_file_path', None)
        return render(request, 'upload.html', {
            'error': 'The file no longer exists. Please upload a new file.'
        })

    initial_abbs = get_init_abb_table(file_path)
    print("DEBUG: Initial abbreviations:\n", initial_abbs, flush=True)
    if initial_abbs.empty:
        initial_abbs = pd.DataFrame(columns=['abbreviation', 'description'])

    # Load abbreviation dictionary
    abb_dict = load_abbreviation_dict()
    print("DEBUG: Initial abb_dict:\n", abb_dict, flush=True)

    doc = Document(file_path)
    text = extract_relevant_text(doc)
    doc_abbs = extract_abbs_from_text(text)
    matched_abbs, unmatched_abbs = separate_abbs(doc_abbs, abb_dict, text)

    # Store initial_abbs and matched_abbs in session to track updates
    request.session['matched_abbs'] = matched_abbs.to_dict('records')
    request.session['initial_abbs'] = initial_abbs.to_dict('records')

    changes = compare_abbreviations(old_abbs=initial_abbs, new_abbs=matched_abbs)
    missing_abbs = changes.get('missing_abbs', pd.DataFrame())
    new_found_abbs = changes.get('new_found', pd.DataFrame())

    return render(
        request,
        'content.html',
        {
            'missing_abbs': missing_abbs.to_dict('records'),
            'new_found_abbs': new_found_abbs.to_dict('records'),
            'unmatched_abbs': unmatched_abbs
        }
    )