import json

from django.test import TestCase
from django.urls import reverse
from docx import Document

from abb_app.models import AbbreviationEntry
from abb_app.services.abbreviations import (
    load_approved_dictionary,
    update_abbreviation_selection,
)
from abb_app.services.extraction import process_abbreviations


class UpdateAbbreviationTests(TestCase):
    def test_repeated_custom_description_is_idempotent(self):
        session = self.client.session
        session['doc_abbs'] = [{
            'abbreviation': 'T4',
            'descriptions': [],
            'selected_description': None,
            'reviewed': False,
            'correct_form': None,
            'highlighted': None,
        }]
        session.save()

        payload = json.dumps({
            'abbreviation': 'T4',
            'description': 'Thyroxine',
            'action': 'add',
        })
        for _ in range(2):
            response = self.client.post(
                reverse('update_abbreviation'),
                data=payload,
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)

        self.assertEqual(
            AbbreviationEntry.objects.filter(
                abbreviation='T4',
                description='Thyroxine',
            ).count(),
            1,
        )

    def test_review_routing_uses_dictionary_spelling_and_description(self):
        cases = [
            ('ATX', 'ATX', 'Existing description', None),
            ('ATX', 'ATX', 'New description', 'ATX'),
            ('АТХ', 'ATX', 'Existing description', None),
            ('АТХ', 'ATX', 'New description', 'АТХ'),
            ('ATX', 'АТХ', 'Existing description', None),
            ('ATX', 'АТХ', 'New description', 'ATX'),
            ('ATX', 'АTX', 'Existing description', None),
            ('ATX', 'АTX', 'New description', 'ATX'),
            (None, 'ЖA', 'New description', 'ЖA'),
        ]

        for approved, incoming, description, expected_review in cases:
            with self.subTest(
                approved=approved,
                incoming=incoming,
                description=description,
            ):
                AbbreviationEntry.objects.all().delete()
                if approved is not None:
                    AbbreviationEntry.objects.create(
                        abbreviation=approved,
                        description='Existing description',
                        status='approved',
                    )

                document = Document()
                document.add_paragraph(incoming)
                processed = process_abbreviations(
                    document,
                    load_approved_dictionary(),
                )
                self.assertEqual(len(processed), 1)

                update_abbreviation_selection(
                    processed,
                    incoming,
                    description,
                    'add',
                )

                reviews = AbbreviationEntry.objects.filter(
                    status='for_review',
                )
                if expected_review is None:
                    self.assertFalse(reviews.exists())
                else:
                    self.assertTrue(reviews.filter(
                        abbreviation=expected_review,
                        description=description,
                    ).exists())
