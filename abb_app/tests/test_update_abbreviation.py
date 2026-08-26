import json

from django.test import TestCase
from docx import Document

from abb_app.models import AbbreviationEntry
from abb_app.services.abbreviations import (
    load_approved_dictionary,
    update_abbreviation_selection,
)
from abb_app.services.extraction import process_abbreviations


class UpdateAbbreviationViewTests(TestCase):
    def setUp(self):
        session = self.client.session
        session['doc_abbs'] = [{
            'abbreviation': 'T4',
            'descriptions': [],
            'selected_description': None,
            'correct_form': None,
            'highlighted': None,
        }]
        session.save()

    def post_json(self, payload):
        return self.client.post(
            '/update_abbreviation/',
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            '/update_abbreviation/',
            data='{',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Invalid JSON')

    def test_unknown_action_returns_400(self):
        response = self.post_json({
            'abbreviation': 'T4',
            'action': 'unknown',
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Invalid action')

    def test_repeated_custom_description_is_idempotent(self):
        payload = {
            'abbreviation': 'T4',
            'description': 'Thyroxine',
            'action': 'add',
        }

        first = self.post_json(payload)
        second = self.post_json(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            AbbreviationEntry.objects.filter(
                abbreviation='T4',
                description='Thyroxine',
            ).count(),
            1,
        )


class ReviewRoutingTests(TestCase):
    def process_abbreviation(self, abbreviation):
        document = Document()
        document.add_paragraph(abbreviation)
        result = process_abbreviations(
            document,
            load_approved_dictionary(),
        )
        self.assertEqual(len(result), 1)
        return result[0]

    def test_review_status_matrix_for_spelling_and_description(self):
        cases = [
            {
                'name': 'exact spelling, existing description',
                'approved_abbreviation': 'ATX',
                'incoming_abbreviation': 'ATX',
                'description': 'Existing description',
                'expected_review': None,
            },
            {
                'name': 'exact spelling, new description',
                'approved_abbreviation': 'ATX',
                'incoming_abbreviation': 'ATX',
                'description': 'New description',
                'expected_review': 'ATX',
            },
            {
                'name': 'homoglyph spelling, existing description',
                'approved_abbreviation': 'АТХ',
                'incoming_abbreviation': 'ATX',
                'description': 'Existing description',
                'expected_review': None,
            },
            {
                'name': 'homoglyph spelling, new description',
                'approved_abbreviation': 'АТХ',
                'incoming_abbreviation': 'ATX',
                'description': 'New description',
                'expected_review': 'АТХ',
            },
            {
                'name': 'Cyrillic homoglyph spelling, existing description',
                'approved_abbreviation': 'ATX',
                'incoming_abbreviation': 'АТХ',
                'description': 'Existing description',
                'expected_review': None,
            },
            {
                'name': 'Cyrillic homoglyph spelling, new description',
                'approved_abbreviation': 'ATX',
                'incoming_abbreviation': 'АТХ',
                'description': 'New description',
                'expected_review': 'ATX',
            },
            {
                'name': 'mixed spelling, existing description',
                'approved_abbreviation': 'ATX',
                'incoming_abbreviation': 'АTX',
                'description': 'Existing description',
                'expected_review': None,
            },
            {
                'name': 'mixed spelling, new description',
                'approved_abbreviation': 'ATX',
                'incoming_abbreviation': 'АTX',
                'description': 'New description',
                'expected_review': 'ATX',
            },
        ]

        for case in cases:
            with self.subTest(case['name']):
                AbbreviationEntry.objects.all().delete()
                AbbreviationEntry.objects.create(
                    abbreviation=case['approved_abbreviation'],
                    description='Existing description',
                    status='approved',
                )
                entry = self.process_abbreviation(
                    case['incoming_abbreviation']
                )

                update_abbreviation_selection(
                    [entry],
                    case['incoming_abbreviation'],
                    case['description'],
                    'add',
                )

                reviews = AbbreviationEntry.objects.filter(status='for_review')
                if case['expected_review'] is None:
                    self.assertFalse(reviews.exists())
                else:
                    self.assertTrue(reviews.filter(
                        abbreviation=case['expected_review'],
                        description=case['description'],
                    ).exists())

    def test_unknown_spelling_is_sent_to_review_unchanged(self):
        for abbreviation in ('АТХ', 'ATX', 'ЖA'):
            with self.subTest(abbreviation=abbreviation):
                AbbreviationEntry.objects.all().delete()
                entry = self.process_abbreviation(abbreviation)
                update_abbreviation_selection(
                    [entry],
                    abbreviation,
                    'New description',
                    'add',
                )

                self.assertTrue(AbbreviationEntry.objects.filter(
                    abbreviation=abbreviation,
                    description='New description',
                    status='for_review',
                ).exists())
