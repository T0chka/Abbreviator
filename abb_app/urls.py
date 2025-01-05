"""
URL configuration for abbr project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from abb_app.views import (
    upload_file, process_and_display,
    update_abbreviation,
    update_difference_section,
    make_abbreviation_table
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', upload_file, name='home'),
    path('upload/', upload_file, name='upload_file'),
    path('process/', process_and_display, name='process_file'),
    path('content/', process_and_display, name='display_content'),
    path('update-abbreviation/', update_abbreviation, name='update_abbreviation'),
    path('update-difference-section/', update_difference_section, name='update_difference_section'),
    path('generate-table/', make_abbreviation_table, name='generate_abbreviation_table'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)