from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html, format_html_join

from .models import AbbreviationEntry
from .services.extraction import CharacterValidator


validator = CharacterValidator()


def approved_homoglyph_conflict(
    abbreviation: str,
    exclude_pk: int | None = None,
) -> str | None:
    homoglyph_key = validator.homoglyph_key(abbreviation)
    queryset = AbbreviationEntry.objects.filter(status='approved')
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)

    for approved_abbreviation in queryset.values_list(
        'abbreviation',
        flat=True,
    ).distinct():
        if approved_abbreviation == abbreviation:
            continue
        if validator.homoglyph_key(approved_abbreviation) == homoglyph_key:
            return approved_abbreviation
    return None


class AbbreviationEntryAdminForm(forms.ModelForm):
    class Meta:
        model = AbbreviationEntry
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        abbreviation = cleaned_data.get('abbreviation')
        status = cleaned_data.get('status')
        if status != 'approved' or not abbreviation:
            return cleaned_data

        conflict = approved_homoglyph_conflict(
            abbreviation,
            exclude_pk=self.instance.pk,
        )
        if conflict is not None:
            self.add_error(
                'abbreviation',
                'В словаре уже есть подтверждённая омоглифическая '
                f'форма: {conflict}.',
            )
        return cleaned_data


@admin.action(description='Approve selected entries')
def approve_entries(modeladmin, request, queryset):
    approved_count = 0
    conflicts: list[str] = []

    for entry in queryset.order_by('pk'):
        conflict = approved_homoglyph_conflict(
            entry.abbreviation,
            exclude_pk=entry.pk,
        )
        if conflict is not None:
            conflicts.append(f'{entry.abbreviation} → {conflict}')
            continue

        if entry.status != 'approved':
            entry.status = 'approved'
            entry.save(update_fields=['status', 'updated_at'])
            approved_count += 1

    if approved_count:
        modeladmin.message_user(
            request,
            f'Подтверждено записей: {approved_count}.',
        )
    if conflicts:
        modeladmin.message_user(
            request,
            'Не подтверждены омоглифические дубликаты: '
            + ', '.join(conflicts),
            level=messages.WARNING,
        )


@admin.register(AbbreviationEntry)
class AbbreviationEntryAdmin(admin.ModelAdmin):
    form = AbbreviationEntryAdminForm
    change_list_template = 'admin/abb_app/abbreviationentry/change_list.html'
    list_display = (
        'colored_abbreviation',
        'description',
        'status',
        'updated_at',
    )
    list_filter = ('status',)
    search_fields = ('abbreviation', 'description')
    ordering = ('abbreviation', 'description', 'status', '-updated_at')
    actions = [approve_entries]
    readonly_fields = ('colored_abbreviation',)

    @admin.display(
        description='Аббревиатура',
        ordering='abbreviation',
    )
    def colored_abbreviation(self, obj):
        if obj is None:
            return '—'

        def render_part(part):
            script = part['script']
            if script:
                script_label = (
                    'кириллица'
                    if script == 'cyrillic'
                    else 'латиница'
                )
                return format_html(
                    '<span class="homoglyph-{}" title="{}">{}</span>',
                    script,
                    script_label,
                    part['char'],
                )
            return format_html('{}', part['char'])

        return format_html_join(
            '',
            '{}',
            ((render_part(part),) for part in validator.homoglyph_parts(
                obj.abbreviation
            )),
        )

    class Media:
        css = {'all': ('css/homoglyphs.css',)}
