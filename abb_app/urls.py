from django.urls import path
from django.conf.urls.static import static
from django.conf import settings

from .views import (
    upload_file, process_file_with_session,
    process_and_display,
    update_abbreviation,
    update_difference_section,
    #validate_abbreviation,
    make_abbreviation_table,
    move_to_unmatched,
    get_unmatched_template
)

urlpatterns = [
    path('', upload_file, name='home'),
    path('upload/', upload_file, name='upload_file'),
    path('process/<str:session_id>/', process_file_with_session, name='process_file_with_session'),
    path('process/<str:session_id>/', process_and_display, name='process_file_with_session'),
    path('update-abbreviation/', update_abbreviation, name='update_abbreviation'),
    path('update-difference-section/', update_difference_section, name='update_difference_section'),
    path('move-to-unmatched/', move_to_unmatched, name='move_to_unmatched'),
    path('get_unmatched_template/', get_unmatched_template, name='get_unmatched_template'),
    path('generate-table/', make_abbreviation_table, name='generate_abbreviation_table'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)