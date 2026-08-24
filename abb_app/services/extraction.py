import re
from collections import Counter
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
            exclude_terms: Set[str] = EXCLUDE_TERMS
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
        
        for i, para in enumerate(doc.paragraphs):
            para_text = para.text.strip()
            if not para_text:
                continue
                
            try:
                style_name = None
                if hasattr(para, 'style') and para.style:
                    try:
                        style_name = para.style.name
                    except:
                        style_name = None
                        
                is_heading = (
                    style_name and 
                    (style_name.startswith('Heading') or 'Заголовок' in style_name)
                )
                
            except Exception:
                is_heading = False
            
            is_bold = False
            if not is_heading:
                for run in para.runs:
                    if run.text.strip() and run.bold:
                        is_bold = True
                        break

            if (is_bold or is_heading):
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
        known_abbreviations: Set[str]
    ) -> Counter[str]:
        """
        Extract abbreviations from text.

        Exact dictionary matches are always included. Unknown tokens must satisfy
        the abbreviation heuristics. Compound and derived forms are removed when
        their standalone abbreviations are already present.
        """
        doc_abbs: Counter[str] = Counter()

        text_no_quotes = re.compile(r'«\S+?»|"[^"]+"').sub('', text)

        for word in text_no_quotes.split():
            candidate = self._clean_abbreviation(word)
            if not candidate:
                continue

            if candidate in known_abbreviations:
                doc_abbs[candidate] += 1
                continue

            if not re.search(r'[A-ZА-ЯЁ].*[A-ZА-ЯЁ]', candidate):
                continue
            if self._is_roman_token(candidate):
                continue
            if candidate in self.exclude_terms:
                continue
            if len(candidate) > 8 and candidate.isalpha():
                continue

            doc_abbs[candidate] += 1

        standalone = set(doc_abbs)

        for candidate in list(doc_abbs):
            if candidate in known_abbreviations:
                continue

            parts = candidate.split('/')
            if (
                len(parts) > 1
                and all(parts)
                and all(part in standalone for part in parts)
            ):
                del doc_abbs[candidate]
                continue

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
                    del doc_abbs[candidate]
                    break

        return doc_abbs

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
            max_contexts: int = 1000
        ) -> List[str]:
        """
        Finds and returns snippets of text around occurrences of the abbreviation.
        Limits the number of contexts returned to `max_contexts`.
        """
        contexts: Set[str] = set()
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
            contexts.add(snippet)
            
        return list(contexts)


class CharacterValidator:
    def __init__(self):
        # Map for character-by-character conversion
        self.cyr2lat = {
            'А': 'A', 'В': 'B', 'С': 'C', 'Е': 'E',
            'Н': 'H', 'К': 'K', 'М': 'M', 'О': 'O',
            'Р': 'P', 'Т': 'T', 'У': 'Y', 'Х': 'X'
        }
        # Add lowercase mappings
        self.cyr2lat.update({k.lower(): v.lower() 
                            for k, v in self.cyr2lat.items()})
        # Create reverse mapping
        self.lat2cyr = {v: k for k, v in self.cyr2lat.items()}

    def validate_abbreviation(
            self, 
            abb: str, 
            abb_dict: List[Abbreviation]
        ) -> dict:
        """
        Validates an abbreviation for mixed characters.
        Checks for existing forms in the dictionary.
        Returns a dict with validation info or empty dict.

        Decision Tree (important returns are shown):
        Abbreviation
        └─ has_cyr_chars OR has_lat_chars
            ├─ Generate forms and search the dictionary
            │    ├─ Match found (does not matter mixed or not)
            │    │    ├─ correct_form = matched_form
            │    │    ├─ descriptions = matched_description
            │    │    └─ highlighted = highlighted_text for tooltip
            │    └─ No match found
            │         ├─ is mixed (has_cyr_chars AND has_lat_chars)
            │         │     └─ highlighted = highlighted_text for moderation
            └─ Does not contain both types of characters or not mixed
                └─ no validation issues found, return empty dict

        Where:
        - `cyr_chars` and `lat_chars` refer to similar-looking
        Cyrillic and Latin characters.
        """
        has_cyr_chars = any(char in self.cyr2lat for char in abb)
        has_lat_chars = any(char in self.lat2cyr for char in abb)
        
        if not (has_cyr_chars or has_lat_chars):
            return {}
    
        # Generate all possible forms and search dictionary
        possible_forms = self._generate_all_mixed_forms(abb)
        matched_entries = [
            entry for entry in abb_dict 
            if entry['abbreviation'] in possible_forms
        ]
    
        if matched_entries:
            # Check for multiple matches
            unique_forms = set(entry['abbreviation'] for entry in matched_entries)
            if len(unique_forms) > 1:
                raise ValueError(
                    "[ERROR] Mixed-character abbreviations in the dictionary:"
                    f"\n{matched_entries}"
                )
            
            matched_entry = matched_entries[0]
            return {
                "correct_form": matched_entry['abbreviation'],
                "descriptions": matched_entry['descriptions'],
                "highlighted": self._highlight_mismatch_characters(
                    abb, matched_entry['abbreviation']
                )
            }

        # Handle case when no dictionary match found but chars are mixed
        if has_cyr_chars and has_lat_chars:
            return {
                "correct_form": None,
                "descriptions": [],
                "highlighted": self._highlight_mixed_characters(abb)
            }

        return {}

    def _generate_all_mixed_forms(self, abb: str) -> set:
        """Generate all possible character combinations"""
        results = set()
        
        # Add full conversions
        results.add("".join(self.lat2cyr.get(ch, ch) for ch in abb))
        results.add("".join(self.cyr2lat.get(ch, ch) for ch in abb))
        
        # Generate partial conversions
        def backtrack(i: int, current: list):
            if i == len(abb):
                results.add("".join(current))
                return

            ch = abb[i]
            # Original character
            current.append(ch)
            backtrack(i + 1, current)
            current.pop()

            # Convert if possible
            if ch in self.cyr2lat:
                current.append(self.cyr2lat[ch])
                backtrack(i + 1, current)
                current.pop()
            if ch in self.lat2cyr:
                current.append(self.lat2cyr[ch])
                backtrack(i + 1, current)
                current.pop()

        backtrack(0, [])
        return results - {abb}  # Exclude original form

    def _highlight_mismatch_characters(
            self, user_abb: str, dict_abb: str
            ) -> list[HighlightedCharacter]:
        """
        Compare each character and return structured rendering metadata
        with mismatch information for template rendering.
        """
        highlighted = []
        for ch_user, ch_dict in zip(user_abb, dict_abb):
            if ch_user != ch_dict:
                mismatch_type = (
                    "кириллическая" if ch_user in self.cyr2lat else "латинская"
                )
                correct_type = (
                    "латинская" if ch_dict in self.lat2cyr else "кириллическая"
                )
                tooltip_text = (
                    f"{ch_user} - {mismatch_type}, "
                    f"в словаре {ch_dict} - {correct_type}"
                )
                highlighted.append({
                    "char": ch_user,
                    "tooltip": tooltip_text,
                    "mismatch": True
                })
            else:
                highlighted.append({
                    "char": ch_user,
                    "mismatch": False
                })
        return highlighted
    
    def _highlight_mixed_characters(
        self,
        abb: str,
    ) -> list[HighlightedCharacter]:
        """Return script metadata when no canonical form is known."""
        highlighted: list[HighlightedCharacter] = []
        for char in abb:
            if char in self.cyr2lat:
                tooltip = f'{char} - кириллическая'
            elif char in self.lat2cyr:
                tooltip = f'{char} - латинская'
            else:
                tooltip = ''

            part: HighlightedCharacter = {
                'char': char,
                'mismatch': False,
            }
            if tooltip:
                part['tooltip'] = tooltip
            highlighted.append(part)

        return highlighted


def process_abbreviations(
        doc: Document,
        abb_dict: List[Abbreviation]
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
    raw_abbs = text_processor.extract_abbreviations(
        text,
        set(dictionary)
    )
    processed_abbs: List[Abbreviation] = []
    
    for abb, count in raw_abbs.items():
        contexts = text_processor.find_abbreviation_context(text, abb)
        
        dict_entry = dictionary.get(abb)
        descriptions = dict_entry['descriptions'] if dict_entry else []
        is_ai_generated = False        
            
        processed_abb: Abbreviation = {
            'abbreviation': abb,
            'descriptions': descriptions,
            'selected_description': None,  # Will be set by user
            'count': count,
            'contexts': contexts,
            'correct_form': None,
            'highlighted': None,
            'status': None,
            'is_ai_generated': is_ai_generated
        }
            
        # Validate and update if it's 9 or less characters long
        if len(abb) <= 15:
            try:
                val_result = validator.validate_abbreviation(abb, abb_dict)
                if val_result:
                    val_descriptions = val_result.get('descriptions', [])
                    processed_abb.update({
                        'correct_form': val_result.get('correct_form'),
                        'highlighted': val_result.get('highlighted'),
                        'descriptions': (
                            val_descriptions if val_descriptions 
                            else processed_abb['descriptions']
                        )
                    })
            except ValueError:
                pass
            
        processed_abbs.append(processed_abb)
    
    return processed_abbs
