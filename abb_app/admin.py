from django.contrib import admin
from .models import AbbreviationEntry

def approve_entries(modeladmin, request, queryset):
        queryset.update(status='approved')
        modeladmin.message_user(request, f"{queryset.count()} entries approved.")
               
@admin.register(AbbreviationEntry)
class AbbreviationEntryAdmin(admin.ModelAdmin):
    list_display = ('abbreviation', 'description', 'status', 'updated_at', 'highlighted')
    list_filter = ('status',)
    search_fields = ('abbreviation', 'description')
    ordering = ('abbreviation', 'description', 'status', '-updated_at')
    actions = [approve_entries]