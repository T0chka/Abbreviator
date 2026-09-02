import json

from django.test import TestCase
from django.urls import reverse

from abb_app.models import AbbreviationEntry
from abb_app.services.abbreviations import (
    format_description,
    load_approved_dictionary,
    normalize_description,
    update_abbreviation_selection,
)
from abb_app.services.extraction import process_abbreviations


class UpdateAbbreviationTests(TestCase):
    def test_repeated_custom_description_is_idempotent_after_normalization(self):
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

        descriptions = ['thyroxine', '  THYROXINE  ']
        for description in descriptions:
            response = self.client.post(
                reverse('update_abbreviation'),
                data=json.dumps({
                    'abbreviation': 'T4',
                    'description': description,
                    'action': 'add',
                }),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)

        reviews = AbbreviationEntry.objects.filter(
            abbreviation='T4',
            status='for_review',
        )
        self.assertEqual(reviews.count(), 1)
        self.assertEqual(reviews.get().description, 'Thyroxine')

    def test_description_normalization_is_independent_of_display_format(self):
        self.assertEqual(
            normalize_description('  Area   Under the Curve  '),
            normalize_description('AREA UNDER THE CURVE'),
        )

    def test_new_description_is_formatted_before_dictionary_review(self):
        doc_abbs = [{
            'abbreviation': 'AUC',
            'descriptions': [],
            'selected_description': None,
            'reviewed': False,
            'correct_form': None,
            'highlighted': None,
        }]

        update_abbreviation_selection(
            doc_abbs,
            'AUC',
            'area under the curve',
            'add',
        )

        self.assertEqual(
            doc_abbs[0]['selected_description'],
            'Area Under the Curve',
        )
        self.assertTrue(AbbreviationEntry.objects.filter(
            abbreviation='AUC',
            description='Area Under the Curve',
            status='for_review',
        ).exists())

    def test_existing_description_is_matched_by_normalized_text(self):
        AbbreviationEntry.objects.create(
            abbreviation='AUC',
            description='Area Under the Curve',
            status='approved',
        )
        processed = process_abbreviations(
            'AUC',
            load_approved_dictionary(),
        )

        update_abbreviation_selection(
            processed,
            'AUC',
            '  AREA   UNDER THE CURVE  ',
            'add',
        )

        self.assertEqual(
            processed[0]['selected_description'],
            'Area Under the Curve',
        )
        self.assertFalse(AbbreviationEntry.objects.filter(
            abbreviation='AUC',
            status='for_review',
        ).exists())

    def test_format_description_handles_cyrillic_abbreviation(self):
        self.assertEqual(
            format_description('АД', 'артериальное давление'),
            'Артериальное давление',
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

                processed = process_abbreviations(
                    incoming,
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
