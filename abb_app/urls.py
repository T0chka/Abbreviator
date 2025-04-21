from django.urls import path
from django.contrib import admin

from .views import (
    upload_file, process_file_with_session,
    update_abbreviation, update_difference_section,
    make_abbreviation_table, dictionary_view,
    generate_description
    )

urlpatterns = [
    path('', upload_file, name='upload_file'),
    path('admin/', admin.site.urls),
    path('process/<str:session_id>/', process_file_with_session, name='process_file_with_session'),
    path('update_abbreviation/', update_abbreviation, name='update_abbreviation'),
    path('update_difference_section/', update_difference_section, name='update_difference_section'),
    path('make_abbreviation_table/', make_abbreviation_table, name='make_abbreviation_table'),
    path('dictionary/', dictionary_view, name='dictionary'),
    path('generate_description/', generate_description, name='generate_description'),
]
