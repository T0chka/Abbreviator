from django.test import SimpleTestCase

from abb_app.utils import CharacterValidator, TextProcessor


class TextProcessorTests(SimpleTestCase):
    def test_dictionary_exact_match_bypasses_heuristics(self):
        processor = TextProcessor()

        result = processor.extract_abbreviations(
            'У пациента определяли уровень T4.',
            {'T4'},
        )

        self.assertEqual(result['T4'], 1)

    def test_unknown_standard_abbreviation_is_detected(self):
        processor = TextProcessor()

        result = processor.extract_abbreviations(
            'Для анализа использовали ABC.',
            set(),
        )

        self.assertEqual(result['ABC'], 1)


class CharacterValidatorTests(SimpleTestCase):
    def test_mixed_alphabet_matches_dictionary_form(self):
        validator = CharacterValidator()
        dictionary = [{
            'abbreviation': 'TNM',
            'descriptions': ['Tumor Node Metastasis'],
        }]

        result = validator.validate_abbreviation('ТNM', dictionary)

        self.assertEqual(result['correct_form'], 'TNM')
        self.assertEqual(
            result['descriptions'],
            ['Tumor Node Metastasis'],
        )