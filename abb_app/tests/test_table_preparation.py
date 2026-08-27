from django.test import SimpleTestCase

from abb_app.services.abbreviations import compare_abbreviations
from abb_app.services.documents import prepare_abbreviation_table_entries
from abb_app.services.extraction import CharacterValidator


CANONICAL = 'CTCAE'
MIXED = 'СTCAE'
SECOND_MIXED = 'CTСAE'
DESCRIPTION = 'common terminology criteria for adverse events'


def mixed_entry(abbreviation=MIXED, description=DESCRIPTION):
    validation = CharacterValidator().validate_abbreviation(
        abbreviation,
        [{
            'abbreviation': CANONICAL,
            'descriptions': [DESCRIPTION],
        }],
    )
    return {
        'abbreviation': abbreviation,
        'descriptions': [DESCRIPTION],
        'selected_description': description,
        'correct_form': validation['correct_form'],
        'highlighted': validation['highlighted'],
    }


def canonical_entry(description=DESCRIPTION):
    return {
        'abbreviation': CANONICAL,
        'descriptions': [DESCRIPTION],
        'selected_description': description,
        'correct_form': None,
        'highlighted': None,
    }


def initial_entry(abbreviation):
    return {
        'abbreviation': abbreviation,
        'descriptions': [DESCRIPTION],
    }


class TablePreparationTests(SimpleTestCase):
    def test_display_and_scope_behavior_matrix(self):
        documents = {
            'W': [mixed_entry()],
            'C': [canonical_entry()],
            'W+C': [mixed_entry(), canonical_entry()],
        }
        initials = {
            'empty': [],
            'C': [initial_entry(CANONICAL)],
            'W': [initial_entry(MIXED)],
            'W+C': [initial_entry(MIXED), initial_entry(CANONICAL)],
        }
        expected = [
            ('W', 'empty', False, {MIXED}, {MIXED}),
            ('W', 'C', False, {MIXED}, {MIXED}),
            ('W', 'W', False, {MIXED}, set()),
            ('W', 'W+C', False, {MIXED}, set()),
            ('W', 'empty', True, {CANONICAL}, {CANONICAL}),
            ('W', 'C', True, {CANONICAL}, set()),
            ('W', 'W', True, {CANONICAL}, {CANONICAL}),
            ('W', 'W+C', True, {CANONICAL}, set()),
            ('C', 'empty', False, {CANONICAL}, {CANONICAL}),
            ('C', 'C', False, {CANONICAL}, set()),
            ('C', 'W', False, {CANONICAL}, {CANONICAL}),
            ('C', 'W+C', False, {CANONICAL}, set()),
            ('C', 'empty', True, {CANONICAL}, {CANONICAL}),
            ('C', 'C', True, {CANONICAL}, set()),
            ('C', 'W', True, {CANONICAL}, {CANONICAL}),
            ('C', 'W+C', True, {CANONICAL}, set()),
            ('W+C', 'empty', False, {MIXED, CANONICAL},
             {MIXED, CANONICAL}),
            ('W+C', 'C', False, {MIXED, CANONICAL}, {MIXED}),
            ('W+C', 'W', False, {MIXED, CANONICAL}, {CANONICAL}),
            ('W+C', 'W+C', False, {MIXED, CANONICAL}, set()),
            ('W+C', 'empty', True, {CANONICAL}, {CANONICAL}),
            ('W+C', 'C', True, {CANONICAL}, set()),
            ('W+C', 'W', True, {CANONICAL}, {CANONICAL}),
            ('W+C', 'W+C', True, {CANONICAL}, set()),
        ]

        for doc_key, initial_key, use_correct, all_names, new_names in expected:
            with self.subTest(
                document=doc_key,
                initial=initial_key,
                use_correct_form=use_correct,
            ):
                common = {
                    'doc_abbs': documents[doc_key],
                    'initial_abbreviations': initials[initial_key],
                    'use_correct_form': use_correct,
                }
                all_rows = prepare_abbreviation_table_entries(
                    **common,
                    scope='all',
                )
                new_rows = prepare_abbreviation_table_entries(
                    **common,
                    scope='new',
                )
                self.assertEqual(
                    {row['abbreviation'] for row in all_rows},
                    all_names,
                )
                self.assertEqual(
                    {row['abbreviation'] for row in new_rows},
                    new_names,
                )

    def test_main_comparison_regression(self):
        initial = [initial_entry(CANONICAL)]
        off = prepare_abbreviation_table_entries(
            [mixed_entry()],
            initial_abbreviations=initial,
            use_correct_form=False,
            scope='all',
        )
        on = prepare_abbreviation_table_entries(
            [mixed_entry()],
            initial_abbreviations=initial,
            use_correct_form=True,
            scope='all',
        )

        off_changes = compare_abbreviations(initial, off)
        on_changes = compare_abbreviations(initial, on)

        self.assertEqual(
            [entry['abbreviation'] for entry in off_changes['missing_abbs']],
            [CANONICAL],
        )
        self.assertEqual(
            [entry['abbreviation'] for entry in off_changes['new_found']],
            [MIXED],
        )
        self.assertEqual(on_changes['missing_abbs'], [])
        self.assertEqual(on_changes['new_found'], [])

    def test_deduplication_is_deterministic(self):
        scenarios = [
            (
                [
                    mixed_entry(description='mixed description'),
                    canonical_entry('canonical description'),
                ],
                CANONICAL,
                'Canonical description',
            ),
            (
                [
                    mixed_entry(MIXED, 'first description'),
                    mixed_entry(SECOND_MIXED, 'second description'),
                ],
                CANONICAL,
                None,
            ),
        ]

        for entries, expected_abbreviation, expected_description in scenarios:
            with self.subTest(entries=[
                entry['abbreviation'] for entry in entries
            ]):
                forward = prepare_abbreviation_table_entries(
                    entries,
                    use_correct_form=True,
                )
                reverse = prepare_abbreviation_table_entries(
                    list(reversed(entries)),
                    use_correct_form=True,
                )

                self.assertEqual(forward, reverse)
                self.assertEqual(len(forward), 1)
                self.assertEqual(
                    forward[0]['abbreviation'],
                    expected_abbreviation,
                )
                if expected_description is not None:
                    self.assertEqual(
                        forward[0]['description'],
                        expected_description,
                    )
