from django.test import SimpleTestCase
from docx import Document

from abb_app.services.extraction import (
    CharacterValidator,
    TextProcessor,
    process_abbreviations,
)


class TextProcessorTests(SimpleTestCase):
    def test_dictionary_exact_match_bypasses_heuristics(self):
        processor = TextProcessor()

        result = processor.extract_abbreviations(
            'У пациента определяли уровень T4.',
            {'T4'},
        )

        self.assertEqual(result['T4'], 1)

    def test_contexts_keep_document_order(self):
        processor = TextProcessor()
        text = 'first-context ABC separator second-context ABC end'

        contexts = processor.find_abbreviation_context(
            text,
            'ABC',
            window=20,
        )

        self.assertEqual(len(contexts), 2)
        self.assertIn('first-context', contexts[0])
        self.assertIn('second-context', contexts[1])

    def test_unknown_standard_abbreviation_is_detected(self):
        processor = TextProcessor()

        result = processor.extract_abbreviations(
            'Для анализа использовали ABC.',
            set(),
        )

        self.assertEqual(result['ABC'], 1)


class CharacterValidatorTests(SimpleTestCase):
    def setUp(self):
        self.validator = CharacterValidator()

    def test_homoglyph_form_matches_dictionary_spelling(self):
        dictionary = [{
            'abbreviation': 'TNM',
            'descriptions': ['Tumor Node Metastasis'],
        }]

        result = self.validator.validate_abbreviation('ТNM', dictionary)

        self.assertEqual(result['correct_form'], 'TNM')
        self.assertEqual(
            result['descriptions'],
            ['Tumor Node Metastasis'],
        )

    def test_exact_dictionary_spelling_has_priority(self):
        dictionary = [
            {'abbreviation': 'ATX', 'descriptions': ['Latin spelling']},
            {'abbreviation': 'АТХ', 'descriptions': ['Cyrillic spelling']},
        ]

        self.assertEqual(
            self.validator.validate_abbreviation('ATX', dictionary),
            {},
        )

    def test_whole_script_homoglyph_form_matches_dictionary_spelling(self):
        dictionary = [{
            'abbreviation': 'АТХ',
            'descriptions': ['Approved description'],
        }]

        result = self.validator.validate_abbreviation('ATX', dictionary)

        self.assertEqual(result['correct_form'], 'АТХ')

    def test_processing_uses_approved_homoglyph_spelling(self):
        document = Document()
        document.add_paragraph('ATX')
        dictionary = [{
            'abbreviation': 'АТХ',
            'descriptions': ['Approved description'],
        }]

        result = process_abbreviations(document, dictionary)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['abbreviation'], 'ATX')
        self.assertEqual(result[0]['correct_form'], 'АТХ')
        self.assertEqual(
            result[0]['descriptions'],
            ['Approved description'],
        )

    def test_processing_does_not_replace_exact_approved_spelling(self):
        document = Document()
        document.add_paragraph('ATX')
        dictionary = [
            {'abbreviation': 'ATX', 'descriptions': ['Exact description']},
            {'abbreviation': 'АТХ', 'descriptions': ['Other description']},
        ]

        result = process_abbreviations(document, dictionary)

        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]['correct_form'])
        self.assertEqual(result[0]['descriptions'], ['Exact description'])

    def test_homoglyph_parts_mark_only_homoglyph_characters(self):
        parts = self.validator.homoglyph_parts('ЖA')

        self.assertEqual(parts, [
            {'char': 'Ж', 'script': ''},
            {'char': 'A', 'script': 'latin'},
        ])
