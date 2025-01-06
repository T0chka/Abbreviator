from django.urls import path
from django.conf.urls.static import static
from django.conf import settings

from .views import (
    upload_file, process_and_display,
    update_abbreviation,
    update_difference_section,
    make_abbreviation_table
)

urlpatterns = [
    path('', upload_file, name='home'),
    path('upload/', upload_file, name='upload_file'),
    path('process/', process_and_display, name='process_file'),
    path('update-abbreviation/', update_abbreviation, name='update_abbreviation'),
    path('update-difference-section/', update_difference_section, name='update_difference_section'),
    path('generate-table/', make_abbreviation_table, name='generate_abbreviation_table'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)