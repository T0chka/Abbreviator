from unittest.mock import patch

from django.contrib import admin
from django.test import RequestFactory, TestCase
from django.urls import reverse

from abb_app.admin import (
    AbbreviationEntryAdmin,
    AbbreviationEntryAdminForm,
    approve_entries,
)
from abb_app.models import AbbreviationEntry


class DictionaryTests(TestCase):
    def test_public_dictionary_shows_only_approved_entries(self):
        AbbreviationEntry.objects.create(
            abbreviation='ЖA',
            description='Approved description',
            status='approved',
        )
        AbbreviationEntry.objects.create(
            abbreviation='XYZ',
            description='Pending description',
            status='for_review',
        )

        response = self.client.get(reverse('dictionary'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dictionary.html')
        self.assertEqual(
            [
                (entry['abbreviation'], entry['description'])
                for entry in response.context['abbreviations']
            ],
            [('ЖA', 'Approved description')],
        )

    def test_admin_allows_same_spelling_but_rejects_homoglyph_alias(self):
        AbbreviationEntry.objects.create(
            abbreviation='АТХ',
            description='Existing description',
            status='approved',
        )
        cases = [
            ('АТХ', True),
            ('ATX', False),
        ]
        for abbreviation, expected_valid in cases:
            with self.subTest(abbreviation=abbreviation):
                form = AbbreviationEntryAdminForm(data={
                    'abbreviation': abbreviation,
                    'description': 'Another description',
                    'status': 'approved',
                })
                self.assertEqual(form.is_valid(), expected_valid)
                if not expected_valid:
                    self.assertIn('abbreviation', form.errors)

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
