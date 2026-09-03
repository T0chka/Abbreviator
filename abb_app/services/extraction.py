import re
from dataclasses import dataclass
from typing import List, Optional, Set

from docx import Document
from docx.text.paragraph import Paragraph

from .abbreviations import Abbreviation, HighlightedCharacter


SKIP_SECTIONS = [
    'СПИСОК ЛИТЕРАТУРЫ',
    'ЛИТЕРАТУРА',
    'ИСПОЛЬЗОВАННАЯ ЛИТЕРАТУРА',
    'СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ',
    'СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ',
    'СПИСОК ИСТОЧНИКОВ',
    'СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ '
    'И ЛИТЕРАТУРЫ',
    'ИСТОЧНИКИ И ЛИТЕРАТУРА',
    'СПИСОК ЦИТИРУЕМОЙ ЛИТЕРАТУРЫ',
    'ЦИТИРУЕМАЯ ЛИТЕРАТУРА',
    'ИСТОЧНИКИ',
    'БИБЛИОГРАФИЯ',
    'БИБЛИОГРАФИЧЕСКИЙ СПИСОК',
    'REFERENCES',
    'BIBLIOGRAPHY',
    'LITERATURE CITED',
    'WORKS CITED',
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
    'СПОНСОРА', 'ЦЕНТРА', 'ТЕРМИНЫ', 'ЦЕЛЬ', 'МЕТОДЫ', 'Санкт-Петербург'
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

SECTION_NUMBER_PREFIX = re.compile(
    r'^\s*(?:(?:\d+(?:\.\d+)*)|(?:[IVXLCDM]+))[.):\s-]+',
    re.IGNORECASE,
)
REFERENCE_NUMBER_PATTERN = re.compile(r'^\s*(?:\[\d+\]|\d+[.)])\s*')
REFERENCE_YEAR_PATTERN = re.compile(
    r'\b(?:18|19|20)\d{2}[a-zа-я]?\b',
    re.IGNORECASE,
)
REFERENCE_IDENTIFIER_PATTERN = re.compile(
    r'\b(?:doi\s*:|pmid\s*:|pmcid\s*:|https?://|www\.)',
    re.IGNORECASE,
)
REFERENCE_INITIALS_PATTERN = re.compile(
    r'\b[A-ZА-ЯЁ]{1,3}\.?(?=\s*[,.;])',
)
REFERENCE_STYLE_TERMS = (
    'bibliograph', 'reference', 'литератур', 'библиограф',
)
QUOTED_TEXT_PATTERN = re.compile(r'«\S+?»|"[^"]+"')
AUTHOR_ET_AL_PATTERN = re.compile(
    r'\.*\s+et\s+al\.?',
    re.IGNORECASE,
)
AUTHOR_COAUTHORS_PATTERN = re.compile(
    r'\.*\s+и\s+соавт\.?',
    re.IGNORECASE,
)
AUTHOR_COMMA_YEAR_PATTERN = re.compile(
    r'\.*\s*,\s*(?:18|19|20)\d{2}[a-zа-я]?\b',
    re.IGNORECASE,
)
AUTHOR_PAREN_YEAR_PATTERN = re.compile(
    r'\.*\s+\((?:18|19|20)\d{2}[a-zа-я]?\)',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExcludedSection:
    section_id: str
    title: str


@dataclass(frozen=True)
class ExtractedText:
    text: str
    excluded_sections: List[ExcludedSection]


@dataclass(frozen=True)
class _ParagraphInfo:
    index: int
    paragraph: Paragraph
    text: str
    style_name: str
    is_heading: bool
    is_bold: bool

    @property
    def is_section_marker(self) -> bool:
        return self.is_heading or self.is_bold

    @property
    def section_id(self) -> str:
        return f'paragraph-{self.index}'


class TextProcessor:
    """Extract relevant text, abbreviations, and contexts from DOCX."""

    def __init__(
        self,
        skip_sections: List[str] = SKIP_SECTIONS,
        exclude_terms: Set[str] = EXCLUDE_TERMS,
    ):
        self.skip_sections = {
            self._normalize_section_title(section)
            for section in skip_sections
        }
        self.exclude_terms = exclude_terms

    def extract_relevant_text(
        self,
        doc: Document,
        included_section_ids: Optional[Set[str]] = None,
    ) -> ExtractedText:
        """Extract text while identifying and excluding bibliography sections.

        A known bibliography title is recognized from normalized paragraph
        text regardless of its Word style. A non-standard title can be
        inferred from a following block of reference-like paragraphs.
        Exclusion ends at the next bold or heading paragraph.
        """
        included = included_section_ids or set()
        infos = self._paragraph_infos(doc)
        bibliography_starts = self._detect_bibliography_sections(infos)

        paragraphs: List[str] = []
        excluded_sections: List[ExcludedSection] = []
        active_section: Optional[ExcludedSection] = None

        for info in infos:
            starts_excluded_section = (
                info.index in bibliography_starts
                and info.section_id not in included
            )

            if active_section is not None and (
                info.is_section_marker or starts_excluded_section
            ):
                excluded_sections.append(active_section)
                active_section = None

            if starts_excluded_section:
                active_section = ExcludedSection(
                    section_id=info.section_id,
                    title=info.text,
                )
                continue

            if active_section is None:
                paragraphs.append(info.text)

        if active_section is not None:
            excluded_sections.append(active_section)
        return ExtractedText(
            text=' '.join(paragraphs),
            excluded_sections=excluded_sections,
        )

    def _paragraph_infos(self, doc: Document) -> List[_ParagraphInfo]:
        infos: List[_ParagraphInfo] = []
        for index, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if not text:
                continue

            style_name = para.style.name if para.style else ''
            is_heading = (
                style_name.startswith('Heading')
                or 'Заголовок' in style_name
            )
            is_bold = (
                not is_heading
                and any(run.text.strip() and run.bold for run in para.runs)
            )
            infos.append(_ParagraphInfo(
                index=index,
                paragraph=para,
                text=text,
                style_name=style_name,
                is_heading=is_heading,
                is_bold=is_bold,
            ))
        return infos

    def _detect_bibliography_sections(
        self,
        infos: List[_ParagraphInfo],
    ) -> Set[int]:
        detected = {
            info.index
            for info in infos
            if self._normalize_section_title(info.text) in self.skip_sections
        }

        for position, info in enumerate(infos):
            if (
                info.index in detected
                or not info.is_section_marker
                or self._is_reference_entry(info)
            ):
                continue

            if self._section_contains_only_references(infos, position):
                detected.add(info.index)

        return detected

    def _section_contains_only_references(
        self,
        infos: List[_ParagraphInfo],
        heading_position: int,
    ) -> bool:
        section_paragraphs: List[_ParagraphInfo] = []
        for info in infos[heading_position + 1:]:
            if info.is_section_marker and not self._is_reference_entry(info):
                break
            section_paragraphs.append(info)

        return len(section_paragraphs) >= 2 and all(
            self._is_reference_entry(info)
            for info in section_paragraphs
        )

    def _is_reference_entry(self, info: _ParagraphInfo) -> bool:
        style_name = info.style_name.casefold()
        if any(term in style_name for term in REFERENCE_STYLE_TERMS):
            return True

        text = info.text
        has_numbering = (
            REFERENCE_NUMBER_PATTERN.search(text) is not None
            or self._has_numbering(info.paragraph)
        )
        has_year = REFERENCE_YEAR_PATTERN.search(text) is not None
        has_identifier = REFERENCE_IDENTIFIER_PATTERN.search(text) is not None
        has_initials = REFERENCE_INITIALS_PATTERN.search(text) is not None

        if has_numbering and (has_year or has_identifier):
            return True
        if self._has_hanging_indent(info.paragraph) and (
            has_year or has_identifier
        ):
            return True
        return has_year and has_initials

    @staticmethod
    def _has_numbering(paragraph: Paragraph) -> bool:
        paragraph_properties = paragraph._p.pPr
        return (
            paragraph_properties is not None
            and paragraph_properties.numPr is not None
        )

    @staticmethod
    def _has_hanging_indent(paragraph: Paragraph) -> bool:
        indent = paragraph.paragraph_format.first_line_indent
        if indent is None and paragraph.style is not None:
            indent = paragraph.style.paragraph_format.first_line_indent
        return indent is not None and indent.pt < 0

    @staticmethod
    def _normalize_section_title(text: str) -> str:
        normalized = text.casefold().replace('ё', 'е').strip()
        normalized = SECTION_NUMBER_PREFIX.sub('', normalized)
        normalized = re.sub(r'[^\w\s]+', ' ', normalized)
        return ' '.join(normalized.split())

    def extract_abbreviations(
        self,
        text: str,
        known_abbreviations: Set[str],
    ) -> List[str]:
        """Extract unique abbreviations in document order."""
        doc_abbs: List[str] = []
        seen: Set[str] = set()
        text_no_quotes = QUOTED_TEXT_PATTERN.sub('', text)

        for token_match in re.finditer(r'\S+', text_no_quotes):
            token = token_match.group()
            candidate = self._clean_abbreviation(token)
            if not candidate:
                continue

            offset = token.find(candidate)
            candidate_start = token_match.start() + offset
            candidate_end = candidate_start + len(candidate)
            if self._is_author_initials(
                text_no_quotes,
                candidate,
                candidate_start,
                candidate_end,
            ):
                continue

            if candidate in seen:
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

    def count_occurrences(self, text: str, abbreviation: str) -> int:
        """Count abbreviation occurrences excluding author initials."""
        pattern = re.compile(
            rf'(?<!\w){re.escape(abbreviation)}(?!\w)'
        )
        return sum(
            1
            for match in pattern.finditer(text)
            if not self._is_author_initials(
                text,
                abbreviation,
                match.start(),
                match.end(),
            )
        )

    @staticmethod
    def _is_author_initials(
        text: str,
        candidate: str,
        start: int,
        end: int,
    ) -> bool:
        initials = candidate.replace('.', '')
        if re.fullmatch(r'[A-ZА-ЯЁ]{1,3}', initials) is None:
            return False

        if start <= 0 or not text[start - 1].isspace():
            return False

        surname_end = start
        while surname_end > 0 and text[surname_end - 1].isspace():
            surname_end -= 1

        surname_start = surname_end
        while surname_start > 0:
            char = text[surname_start - 1]
            if char.isalpha() or char in "-'’":
                surname_start -= 1
                continue
            break

        surname = text[surname_start:surname_end]
        if re.fullmatch(
            r"[^\W\d_]+(?:[-'’][^\W\d_]+)*",
            surname,
            re.UNICODE,
        ) is None:
            return False
        letters = [char for char in surname if char.isalpha()]
        if (
            not letters
            or not letters[0].isupper()
            or not any(char.islower() for char in letters)
        ):
            return False

        if AUTHOR_ET_AL_PATTERN.match(text, end):
            return True
        if AUTHOR_COAUTHORS_PATTERN.match(text, end):
            return True

        return bool(
            AUTHOR_COMMA_YEAR_PATTERN.match(text, end)
            or AUTHOR_PAREN_YEAR_PATTERN.match(text, end)
        )

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
        """Clean and format an abbreviation token."""
        clean_match = match.strip(':;,.»«][')

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
        """Return context snippets in document order."""
        contexts: List[str] = []
        matches = re.finditer(
            rf'(?<!\w){re.escape(abbreviation)}(?!\w)',
            text,
        )
        for match in matches:
            start = max(0, match.start() - window)
            end = min(len(text), match.end() + window)
            snippet = text[start:end].strip()
            if start > 0:
                snippet = f'...{snippet}'
            if end < len(text):
                snippet = f'{snippet}...'
            contexts.append(snippet)
            if len(contexts) >= max_contexts:
                break

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
    text: str,
    abb_dict: List[Abbreviation],
) -> List[Abbreviation]:
    """Process abbreviations found in relevant document text."""
    text_processor = TextProcessor()
    validator = CharacterValidator()
    dictionary = {
        entry['abbreviation']: entry
        for entry in abb_dict
    }

    raw_abbs = text_processor.extract_abbreviations(
        text,
        set(dictionary),
    )
    processed_abbs: List[Abbreviation] = []

    for abb in raw_abbs:
        contexts = text_processor.find_abbreviation_context(
            text,
            abb,
        )
        dict_entry = dictionary.get(abb)
        descriptions = dict_entry['descriptions'] if dict_entry else []

        processed_abb: Abbreviation = {
            'abbreviation': abb,
            'descriptions': descriptions,
            'selected_description': None,
            'reviewed': False,
            'occurrence_count': text_processor.count_occurrences(
                text,
                abb,
            ),
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
