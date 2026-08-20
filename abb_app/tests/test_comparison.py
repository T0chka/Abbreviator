from django.test import SimpleTestCase

from abb_app.utils import compare_abbreviations


class AbbreviationComparisonTests(SimpleTestCase):
    def test_reports_missing_and_new_abbreviations(self):
        old_abbs = [
            {
                'abbreviation': 'ABC',
                'descriptions': ['Alpha beta complex'],
            },
            {
                'abbreviation': 'T4',
                'descriptions': ['Thyroxine'],
            },
        ]
        new_abbs = [
            {
                'abbreviation': 'T4',
                'description': 'Thyroxine',
            },
            {
                'abbreviation': 'MRI',
                'description': 'Magnetic resonance imaging',
            },
        ]

        result = compare_abbreviations(old_abbs, new_abbs)

        self.assertEqual(result['missing_abbs'], [old_abbs[0]])
        self.assertEqual(
            result['new_found'],
            [{
                'abbreviation': 'MRI',
                'descriptions': ['Magnetic resonance imaging'],
            }],
        )