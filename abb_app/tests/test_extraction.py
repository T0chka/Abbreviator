from django.test import SimpleTestCase
from docx import Document

from abb_app.services.extraction import (
    CharacterValidator,
    TextProcessor,
    process_abbreviations,
)


class TextProcessorTests(SimpleTestCase):
    def test_extracts_known_and_standard_unknown_abbreviations(self):
        processor = TextProcessor()

        result = processor.extract_abbreviations(
            'У пациента определяли T4 и ABC.',
            {'T4'},
        )

        self.assertEqual(result, ['T4', 'ABC'])

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


class CharacterValidatorTests(SimpleTestCase):
    def setUp(self):
        self.validator = CharacterValidator()

    def test_homoglyph_resolution_matches_approved_spelling(self):
        cases = [
            (
                'ТNM',
                [{
                    'abbreviation': 'TNM',
                    'descriptions': ['Tumor Node Metastasis'],
                }],
                'TNM',
                ['Tumor Node Metastasis'],
            ),
            (
                'ATX',
                [{
                    'abbreviation': 'АТХ',
                    'descriptions': ['Approved description'],
                }],
                'АТХ',
                ['Approved description'],
            ),
        ]

        for incoming, dictionary, correct_form, descriptions in cases:
            with self.subTest(incoming=incoming):
                result = self.validator.validate_abbreviation(
                    incoming,
                    dictionary,
                )
                self.assertEqual(result['correct_form'], correct_form)
                self.assertEqual(result['descriptions'], descriptions)

    def test_processing_respects_exact_homoglyph_and_long_dictionary_forms(self):
        cases = [
            {
                'text': 'ATX',
                'dictionary': [{
                    'abbreviation': 'АТХ',
                    'descriptions': ['Approved description'],
                }],
                'correct_form': 'АТХ',
                'descriptions': ['Approved description'],
            },
            {
                'text': 'ATX',
                'dictionary': [
                    {
                        'abbreviation': 'ATX',
                        'descriptions': ['Exact description'],
                    },
                    {
                        'abbreviation': 'АТХ',
                        'descriptions': ['Other description'],
                    },
                ],
                'correct_form': None,
                'descriptions': ['Exact description'],
            },
            {
                'text': 'ATX-ATX-ATX-ATX-ATX',
                'dictionary': [{
                    'abbreviation': 'АТХ-АТХ-АТХ-АТХ-АТХ',
                    'descriptions': ['Long description'],
                }],
                'correct_form': 'АТХ-АТХ-АТХ-АТХ-АТХ',
                'descriptions': ['Long description'],
            },
        ]

        for case in cases:
            with self.subTest(text=case['text']):
                document = Document()
                document.add_paragraph(case['text'])

                result = process_abbreviations(
                    document,
                    case['dictionary'],
                )

                self.assertEqual(len(result), 1)
                self.assertEqual(
                    result[0]['correct_form'],
                    case['correct_form'],
                )
                self.assertEqual(
                    result[0]['descriptions'],
                    case['descriptions'],
                )
