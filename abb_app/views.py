from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from docx import Document

def upload_file(request):
    if request.method == 'POST' and request.FILES.get('uploaded_file'):
        uploaded_file = request.FILES['uploaded_file']
        fs = FileSystemStorage()
        filename = fs.save(uploaded_file.name, uploaded_file)
        request.session['uploaded_file_path'] = fs.path(filename)
        return redirect('display_content')
    return render(request, 'upload.html')


def display_content(request):
    file_path = request.session.get('uploaded_file_path')
    content = None
    error = None

    if file_path:
        try:
            doc = Document(file_path)
            content = [para.text for para in doc.paragraphs[:10]]
        except Exception as e:
            error = str(e)

    return render(request, 'content.html', {'content': content, 'error': error})