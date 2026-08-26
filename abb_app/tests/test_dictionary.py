from unittest.mock import patch

from django.contrib import admin
from django.test import RequestFactory, TestCase

from abb_app.admin import (
    AbbreviationEntryAdmin,
    AbbreviationEntryAdminForm,
    approve_entries,
)
from abb_app.models import AbbreviationEntry
from abb_app.views import dictionary_view


class DictionaryViewTests(TestCase):
    def test_dictionary_colors_only_homoglyph_letters(self):
        AbbreviationEntry.objects.create(
            abbreviation='ЖA',
            description='Test description',
            status='approved',
        )

        request = RequestFactory().get('/dictionary/')
        response = dictionary_view(request)
        html = response.content.decode()

        self.assertIn('<span>Ж</span>', html)
        self.assertIn(
            '<span class="homoglyph-latin" title="латиница">A</span>',
            html,
        )
        self.assertNotIn('openSuggestForm', html)
        self.assertNotIn('material-icons">edit', html)


class DictionaryAdminTests(TestCase):
    def test_approved_homoglyph_duplicate_is_rejected(self):
        AbbreviationEntry.objects.create(
            abbreviation='АТХ',
            description='Existing description',
            status='approved',
        )

        form = AbbreviationEntryAdminForm(data={
            'abbreviation': 'ATX',
            'description': 'Another description',
            'status': 'approved',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('abbreviation', form.errors)

    def test_same_approved_spelling_can_have_another_description(self):
        AbbreviationEntry.objects.create(
            abbreviation='АТХ',
            description='Existing description',
            status='approved',
        )

        form = AbbreviationEntryAdminForm(data={
            'abbreviation': 'АТХ',
            'description': 'Another description',
            'status': 'approved',
        })

        self.assertTrue(form.is_valid(), form.errors)

    def test_bulk_approval_skips_homoglyph_duplicate(self):
        AbbreviationEntry.objects.create(
            abbreviation='АТХ',
            description='Existing description',
            status='approved',
        )
        review = AbbreviationEntry.objects.create(
            abbreviation='ATX',
            description='Review description',
            status='for_review',
        )
        model_admin = AbbreviationEntryAdmin(
            AbbreviationEntry,
            admin.site,
        )
        request = RequestFactory().post('/admin/')

        with patch.object(model_admin, 'message_user'):
            approve_entries(
                model_admin,
                request,
                AbbreviationEntry.objects.filter(pk=review.pk),
            )

        review.refresh_from_db()
        self.assertEqual(review.status, 'for_review')
