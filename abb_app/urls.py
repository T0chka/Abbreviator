from django.contrib import admin
from django.urls import path

from .views import (
    dictionary_view,
    download_demo_document,
    end_document_session,
    generate_description,
    make_abbreviation_table,
    process_file_with_session,
    touch_document_session,
    update_abbreviation,
    update_difference_section,
    upload_file,
)

urlpatterns = [
    path('', upload_file, name='upload_file'),
    path('admin/', admin.site.urls),
    path('demo/document/', download_demo_document,
         name='download_demo_document'),
    path('dictionary/', dictionary_view, name='dictionary'),
    path('generate_description/', generate_description,
         name='generate_description'),
    path('make_abbreviation_table/', make_abbreviation_table,
         name='make_abbreviation_table'),
    path('process/<str:session_id>/', process_file_with_session,
         name='process_file_with_session'),
    path('session/end/', end_document_session,
         name='end_document_session'),
    path('session/touch/', touch_document_session,
         name='touch_document_session'),
    path('update_abbreviation/', update_abbreviation,
         name='update_abbreviation'),
    path('update_difference_section/', update_difference_section,
         name='update_difference_section'),
]
