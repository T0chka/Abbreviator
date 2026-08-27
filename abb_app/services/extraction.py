import re
from typing import List, Set

from docx import Document

from .abbreviations import Abbreviation, HighlightedCharacter


SKIP_SECTIONS = [
    'СПИСОК ЛИТЕРАТУРЫ', 'Список использованной литературы',
    'Список использованных источников'
]
EXCLUDE_TERMS = {
    'ДИЗАЙН', 'ГЛАВНЫЙ', 'СПИСОК', 'ПРЯМОЙ', 'ПРИЕМ', 'ПРОТОКОЛ', 'ОТБОР',
    'КАЧЕСТВА', 'ПЕРИОД', 'ВЕДЕНИЕ', 'ЭТАП', 'ЭТИКА', 'СИНОПСИС', 'ЛИСТ',
    'ЦЕЛИ', 'РАБОТА', 'ИСТОРИЯ', 'ОЦЕНКА', 'СПОНСОР', 'ЗАДАЧИ', 'ДОСТУП',
    'КОНТРОЛЬ', 'ТЕРМИНОВ', 'ЗАПИСЕЙ', 'ГИПОТЕЗА', 'ДАННЫМИ', 'ДЕЙСТВИЕ',
    'ДАННЫМ/ДОКУМЕНТАЦИИ', 'ДЛЯ', 'ФОРМА', 'ВВЕДЕНИЕ', 'СВОЙСТВА', 'РЕЗЮМЕ',
    'ДАННЫХ', 'ЧЕЛОВЕКА', 'ОБЩЕСТВО', 'ЦЕНТР', 'АКТИВНЫХ', 'ВЕЩЕСТВ',
    'НАУЧНЫЙ', 'ОТЧЕТ', 'ОБЗОР', 'Каплана-Мейера', 'Стивенса-Джонсона',
    'Спрейг-Доули', 'Спрег-Доули', 'Мантеля-Хензеля', 'Нью-Йоркской',
    'Лонг-Эванс', 'ГмбХ', 'ТАБЛИЦ', 'РИСУНКОВ', 'ДАННЫЕ', 'СТРАНИЦА',
    'СПОНСОРА', 'ЦЕНТРА', 'ТЕРМИНЫ', 'ЦЕЛЬ'
}

ROMAN_NUMERAL_PATTERN = re.compile(
    r'(?=[IVXLCDM]+$)M{0,3}(?:CM|CD|D?C{0,3})'
    r'(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})',
    re.IGNORECASE
)
ROMAN_STAGE_PATTERN = re.compile(
    r'(?=[IVXLCDM]+[ABCАВС]$)'
    r'M{0,3}(?:CM|CD|D?C{0,3})'
    r'(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})'
    r'[ABCАВС]',
    re.IGNORECASE
)


class TextProcessor:
    """
    Class for extracting a relevant text, abbreviations and their contexts from
    a Word document.
    """
    def __init__(
        self,
        skip_sections: List[str] = SKIP_SECTIONS,
        exclude_terms: Set[str] = EXCLUDE_TERMS,
    ):
        self.skip_sections = {
            section.upper() for section in skip_sections
        }
        self.exclude_terms = exclude_terms

    def extract_relevant_text(self, doc: Document) -> str:
        """
        Extracts text from the document, excluding `skip_sections`.
        The exclusion starts at the section title in bold or heading style
        and resumes at the next bold or heading section.
        """
        paragraphs = []
        skip = False

        for para in doc.paragraphs:
            para_text = para.text.strip()
            if not para_text:
                continue

            style_name = para.style.name if para.style else ''
            is_heading = (
                style_name.startswith('Heading')
                or 'Заголовок' in style_name
            )

            is_bold = False
            if not is_heading:
                for run in para.runs:
                    if run.text.strip() and run.bold:
                        is_bold = True
                        break

            if is_bold or is_heading:
                para_text_upper = para_text.upper()
                if any(section in para_text_upper for section in self.skip_sections):
                    skip = True
                elif skip:
                    skip = False

            if not skip:
                paragraphs.append(para_text)

        return ' '.join(paragraphs)

    def extract_abbreviations(
        self,
        text: str,
        known_abbreviations: Set[str],
    ) -> List[str]:
        """Extract unique abbreviations in document order."""
        doc_abbs: List[str] = []
        seen: Set[str] = set()
        text_no_quotes = re.compile(r'«\S+?»|"[^"]+"').sub('', text)

        for word in text_no_quotes.split():
            candidate = self._clean_abbreviation(word)
            if not candidate or candidate in seen:
                continue

            if candidate not in known_abbreviations:
                if not re.search(r'[A-ZА-ЯЁ].*[A-ZА-ЯЁ]', candidate):
                    continue
                if self._is_roman_token(candidate):
                    continue
                if candidate in self.exclude_terms:
                    continue
                if len(candidate) > 8 and candidate.isalpha():
                    continue

            seen.add(candidate)
            doc_abbs.append(candidate)

        standalone = set(doc_abbs)
        filtered: List[str] = []

        for candidate in doc_abbs:
            if candidate in known_abbreviations:
                filtered.append(candidate)
                continue

            parts = candidate.split('/')
            if (
                len(parts) > 1
                and all(parts)
                and all(part in standalone for part in parts)
            ):
                continue

            is_derived = False
            for abbreviation in standalone:
                if abbreviation == candidate:
                    continue

                if candidate.startswith(f'{abbreviation}-'):
                    affix = candidate[len(abbreviation) + 1:]
                elif candidate.endswith(f'-{abbreviation}'):
                    affix = candidate[:-len(abbreviation) - 1]
                else:
                    continue

                if (
                    len(affix) >= 2
                    and re.fullmatch(r'[А-Яа-яЁё]+', affix)
                    and re.search(r'[а-яё]', affix)
                ):
                    is_derived = True
                    break

            if not is_derived:
                filtered.append(candidate)

        return filtered

    @staticmethod
    def _is_roman_token(candidate: str) -> bool:
        parts = candidate.split('-')
        if len(parts) > 2:
            return False
        return all(
            ROMAN_NUMERAL_PATTERN.fullmatch(part)
            or ROMAN_STAGE_PATTERN.fullmatch(part)
            for part in parts
        )

    def _clean_abbreviation(self, match: str) -> str:
        """Helper method to clean and format abbreviation matches."""
        clean_match = match.strip(':;,.»«][')

        # Remove '(' and ')' if unmatched, e.g. 'IgG)' but not in 'IgG(1)'
        if clean_match.startswith('('):
            clean_match = clean_match[1:]
        if clean_match.endswith(')') and clean_match.count('(') == 0:
            clean_match = re.sub(r'\)+$', '', clean_match)

        return clean_match.strip('»«][')

    def find_abbreviation_context(
        self,
        text: str,
        abbreviation: str,
        window: int = 150,
        max_contexts: int = 1000,
    ) -> List[str]:
        """
        Finds and returns snippets of text around occurrences of the abbreviation.
        Limits the number of contexts returned to `max_contexts`.
        """
        contexts: List[str] = []
        seen_contexts: Set[str] = set()
        matches = re.finditer(
            rf'(?<!\w){re.escape(abbreviation)}(?!\w)', text
        )
        for match in matches:
            start = max(0, match.start() - window)
            end = min(len(text), match.end() + window)
            snippet = text[start:end].strip()
            if start > 0:
                snippet = f'...{snippet}'
            if end < len(text):
                snippet = f'{snippet}...'
            if max_contexts == 1:
                return [snippet]
            if snippet not in seen_contexts:
                seen_contexts.add(snippet)
                contexts.append(snippet)

        return contexts


class CharacterValidator:
    def __init__(self):
        self.cyr2lat = {
            'А': 'A', 'В': 'B', 'С': 'C', 'Е': 'E',
            'Н': 'H', 'К': 'K', 'М': 'M', 'О': 'O',
            'Р': 'P', 'Т': 'T', 'У': 'Y', 'Х': 'X'
        }
        self.cyr2lat.update({
            key.lower(): value.lower()
            for key, value in self.cyr2lat.items()
        })
        self.lat2cyr = {value: key for key, value in self.cyr2lat.items()}

    def validate_abbreviation(
        self,
        abb: str,
        abb_dict: List[Abbreviation],
    ) -> dict:
        """Return a known homoglyph-equivalent spelling, if one exists.

        An exact approved dictionary spelling always has priority. Only when
        the exact spelling is absent is its homoglyph-normalized spelling
        compared with the approved dictionary.
        """
        if any(entry['abbreviation'] == abb for entry in abb_dict):
            return {}

        homoglyph_key = self.homoglyph_key(abb)
        matched_entries = [
            entry for entry in abb_dict
            if (
                entry['abbreviation'] != abb
                and self.homoglyph_key(entry['abbreviation']) == homoglyph_key
            )
        ]
        if not matched_entries:
            return {}

        unique_forms = {entry['abbreviation'] for entry in matched_entries}
        if len(unique_forms) > 1:
            raise ValueError(
                '[ERROR] Homoglyph-equivalent abbreviations in the dictionary:'
                f'\n{matched_entries}'
            )

        matched_entry = matched_entries[0]
        return {
            'correct_form': matched_entry['abbreviation'],
            'descriptions': matched_entry['descriptions'],
            'highlighted': self._highlight_mismatch_characters(
                abb, matched_entry['abbreviation']
            ),
        }

    def homoglyph_key(self, abb: str) -> str:
        """Normalize Cyrillic homoglyphs to their Latin counterparts."""
        return ''.join(self.cyr2lat.get(char, char) for char in abb)

    def homoglyph_parts(self, abb: str) -> list[dict[str, str]]:
        """Return script metadata only for Cyrillic/Latin homoglyphs."""
        parts: list[dict[str, str]] = []
        for char in abb:
            if char in self.cyr2lat:
                script = 'cyrillic'
            elif char in self.lat2cyr:
                script = 'latin'
            else:
                script = ''
            parts.append({'char': char, 'script': script})
        return parts

    def _highlight_mismatch_characters(
        self,
        user_abb: str,
        dict_abb: str,
    ) -> list[HighlightedCharacter]:
        """Mark characters that differ from the approved spelling."""
        highlighted: list[HighlightedCharacter] = []
        for user_char, dict_char in zip(user_abb, dict_abb):
            if user_char != dict_char:
                user_script = (
                    'кириллическая'
                    if user_char in self.cyr2lat
                    else 'латинская'
                )
                dict_script = (
                    'латинская'
                    if dict_char in self.lat2cyr
                    else 'кириллическая'
                )
                highlighted.append({
                    'char': user_char,
                    'tooltip': (
                        f'{user_char} - {user_script}, '
                        f'в словаре {dict_char} - {dict_script}'
                    ),
                    'mismatch': True,
                })
            else:
                highlighted.append({
                    'char': user_char,
                    'mismatch': False,
                })
        return highlighted


def process_abbreviations(
    doc: Document,
    abb_dict: List[Abbreviation],
) -> List[Abbreviation]:
    """Process abbreviations found in document"""
    text_processor = TextProcessor()
    validator = CharacterValidator()

    # Get abbreviations from document text
    dictionary = {
        entry['abbreviation']: entry
        for entry in abb_dict
    }

    text = text_processor.extract_relevant_text(doc)
    raw_abbs = text_processor.extract_abbreviations(text, set(dictionary))
    processed_abbs: List[Abbreviation] = []

    for abb in raw_abbs:
        contexts = text_processor.find_abbreviation_context(text, abb)
        dict_entry = dictionary.get(abb)
        descriptions = dict_entry['descriptions'] if dict_entry else []

        processed_abb: Abbreviation = {
            'abbreviation': abb,
            'descriptions': descriptions,
            'selected_description': None,
            'reviewed': False,
            'contexts': contexts,
            'correct_form': None,
            'highlighted': None,
        }

        if dict_entry is None:
            validation = validator.validate_abbreviation(abb, abb_dict)
            if validation:
                processed_abb.update({
                    'correct_form': validation.get('correct_form'),
                    'highlighted': validation.get('highlighted'),
                    'descriptions': validation.get('descriptions', []),
                })

        processed_abbs.append(processed_abb)

    return processed_abbs
