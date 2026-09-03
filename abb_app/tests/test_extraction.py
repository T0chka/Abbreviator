from django.test import SimpleTestCase

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

    def test_author_initials_are_not_treated_as_abbreviations(self):
        text = (
            'Liu TT et al. compared ABC. '
            'Cornelison LE, 2020 reported ABC. '
            'Иванов АА и соавт. оценивали АД. '
            'TT повышался после стимуляции. '
            'Иванов АД сообщил результат. '
            'TT, 2022. АД и др. параметры.'
        )

        result = process_abbreviations(text, [])
        entries = {entry['abbreviation']: entry for entry in result}

        self.assertNotIn('LE', entries)
        self.assertNotIn('АА', entries)
        self.assertIn('TT', entries)
        self.assertEqual(entries['TT']['occurrence_count'], 2)
        self.assertIn('ABC', entries)
        self.assertIn('АД', entries)

    def test_author_initial_check_avoids_full_document_slices(self):
        class BoundedSliceText(str):
            def __getitem__(self, key):
                if (
                    isinstance(key, slice)
                    and (key.start is None or key.stop is None)
                ):
                    raise AssertionError('Unbounded document slice')
                return super().__getitem__(key)

        text = BoundedSliceText(
            ('ordinary text ' * 1000) + 'Liu TT et al. compared ABC.'
        )
        start = text.index('TT')

        self.assertTrue(
            TextProcessor._is_author_initials(
                text,
                'TT',
                start,
                start + 2,
            )
        )

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

    def test_contexts_keep_duplicate_occurrences_for_display_grouping(self):
        processor = TextProcessor()
        text = 'prefix zz ABC yy middle zz ABC yy suffix'

        contexts = processor.find_abbreviation_context(
            text,
            'ABC',
            window=3,
        )

        self.assertEqual(contexts, [
            '...zz ABC yy...',
            '...zz ABC yy...',
        ])


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
                result = process_abbreviations(
                    case['text'],
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
