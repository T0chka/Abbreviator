import os
import re
import pandas as pd
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from thefuzz import process, fuzz
from collections import Counter
from typing import (
    Union, List, Dict, Set, Counter, Optional, 
    Tuple, Any, Iterator
)
from pandas import DataFrame
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P

ABB_DICT_PATH = os.path.join(
    os.path.dirname(__file__),
    'data', 'abb_dict.csv'
)
SECTION_PATTERNS = [
    'ПЕРЕЧЕНЬ СОКРАЩЕНИЙ И ОПРЕДЕЛЕНИЯ ТЕРМИНОВ', 'СПИСОК СОКРАЩЕНИЙ'
]
SKIP_SECTIONS = [
    "СПИСОК ЛИТЕРАТУРЫ", "Список использованной литературы",
    "Список использованных источников"
]
EXCLUDE_TERMS = {
    'ДИЗАЙН', 'ГЛАВНЫЙ', 'СПИСОК', 'ПРЯМОЙ', 'ПРИЕМ', 'ПРОТОКОЛ', 'ОТБОР',
    'КАЧЕСТВА', 'ПЕРИОД', 'ВЕДЕНИЕ', 'ЭТАП', 'ЭТИКА', 'СИНОПСИС', 'ЛИСТ',
    'ЦЕЛИ', 'РАБОТА', 'ИСТОРИЯ', 'ОЦЕНКА', 'СПОНСОР', 'ЗАДАЧИ', 'ДОСТУП',
    'КОНТРОЛЬ', 'ТЕРМИНОВ', 'ЗАПИСЕЙ', 'ГИПОТЕЗА', 'ДАННЫМИ', 'ДЕЙСТВИЕ',
    'ДАННЫМ/ДОКУМЕНТАЦИИ', 'ДЛЯ', 'ФОРМА', 'ВВЕДЕНИЕ', 'СВОЙСТВА', 'РЕЗЮМЕ',
    'ДАННЫХ', 'ЧЕЛОВЕКА'
}

def load_abbreviation_dict() -> DataFrame:
    """
    Load abbreviations from CSV, or return empty DataFrame if not found.
    """
    if os.path.exists(ABB_DICT_PATH):
        return pd.read_csv(ABB_DICT_PATH)
    else:
        print(
            f"[WARNING] Abbreviation dictionary not found at: {ABB_DICT_PATH}.",
            "Returning empty DataFrame."
        )
        return pd.DataFrame(columns=["abbreviation", "description"])

# -----------------------------------------------------------------------------
# Abbreviation table extraction
# -----------------------------------------------------------------------------

class AbbreviationTableExtractor:
    NS = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    }

    def __init__(self, section_patterns: List[str] = SECTION_PATTERNS):
        self.section_patterns = section_patterns

    def extract_table_element(self, doc: Document) -> Optional[CT_Tbl]:
        """
        Extract the first table following a section matching `section_patterns`.
        Returns the block containing the table, or None if not found.
        """
        found_section = False
        
        for block in doc.element.body:
            if block.tag.endswith('p'): # paragraph block
                para_text = ''.join(
                    node.text for node in block.findall(
                        './/w:t', namespaces=self.NS
                    ) if node.text
                ).strip()

                if any(pattern.casefold() in para_text.casefold()
                    for pattern in self.section_patterns):
                    
                    # Must NOT have a hyperlink (avoid ToC lines)
                    if block.find('.//w:hyperlink', namespaces=self.NS) is not None:
                        continue
                    
                    # Must NOT end with a digit (avoid missformated ToC)
                    if para_text.strip().endswith(tuple("0123456789")):
                        continue
                    
                    # Must have some heading indication (pStyle or outlineLvl)
                    para_style = block.find('.//w:pStyle', namespaces=self.NS)
                    outline_level = block.find('.//w:outlineLvl', namespaces=self.NS)
                    if para_style is not None or outline_level is not None:
                        found_section = True
                        continue

            if found_section and block.tag.endswith('tbl'):
                return block

        return None

    def parse_table(self,table_element: CT_Tbl) -> DataFrame:
        """
        Parse an lxml table element, and return it as a DataFrame
        with two columns: [abbreviation, description].
        """
        rows_data: List[List[str]] = []
        first_row = True

        for row in table_element.findall('.//w:tr', namespaces=self.NS):
            cell_texts = []
            for cell in row.findall('.//w:tc', namespaces=self.NS):
                texts = [
                    t.text for t in cell.findall('.//w:t', namespaces=self.NS)
                    if t.text
                ]
                cell_text = ''.join(texts).strip()
                cell_texts.append(cell_text)

            if first_row and cell_texts[:2] == ["Аббревиатура", "Расшифровка"]:
                first_row = False
                continue

            rows_data.append(cell_texts)

        if len(rows_data) > 0 and len(rows_data[0]) == 2:
            return pd.DataFrame(rows_data, columns=['abbreviation', 'description'])
        else:
            return pd.DataFrame(columns=['abbreviation', 'description'])
        
    def get_abbreviation_table(self, file_path: str) -> DataFrame:
        """
        Extract, parse, clean, and return the relevant table from the doc,
        as a DataFrame with columns ['abbreviation', 'description'].
        """
        doc = Document(os.path.abspath(file_path))
        table_element = self.extract_table_element(doc)

        if table_element is None:
            print(f"[INFO] No relevant abbreviation table found in: {file_path}")
            return pd.DataFrame(columns=['abbreviation', 'description'])

        df = self.parse_table(table_element)
        if df.empty:
            print(
                "[WARNING] Parsed table was malformed",
                f"returning empty DataFrame for: {file_path}"
            )
        return df

# -----------------------------------------------------------------------------
# Text, abbreviation, and context extraction
# -----------------------------------------------------------------------------

class TextProcessor:
    def __init__(
            self,
            skip_sections: List[str] = SKIP_SECTIONS,
            exclude_terms: Set[str] = EXCLUDE_TERMS
        ):
        self.skip_sections = skip_sections
        self.exclude_terms = exclude_terms
        self.roman_pattern = re.compile(
            r'^(?:[IVXLCDM]+(?:-[IVXLCDM]+)?)[A-Za-zА-Яа-яёЁ]*$',
            re.IGNORECASE
        )

    def extract_relevant_text(self, doc: Document) -> str:
        """
        Extracts text from the document, excluding `skip_sections`.
        The exclusion starts at the section title in bold or heading style
        and resumes at the next bold or heading section.
        """
        relevant_text: List[str] = []
        skip: bool = False

        for para in doc.paragraphs:
            para_text = para.text.strip()

            is_heading = (
                para.style.name.startswith('Heading')
                or 'Заголовок' in para.style.name
            )
            is_bold = any(
                run.bold for run in para.runs if run.text.strip()
            )

            if any(t.upper() in para_text.upper() for t in self.skip_sections):
                print(
                    f"Detected: {para_text[:100]} - "
                    f"Style: {para.style.name} - "
                    f"Is Bold: {is_bold} - Is Heading: {is_heading}"
                )
            if ((is_bold or is_heading)
                and any(t.upper() in para_text.upper() for t in self.skip_sections)
                ):
                print("Skipping this section")
                skip = True

            elif (is_bold or is_heading) and skip:
                print(
                    f"\nResuming search at section: {para_text}"
                )
                skip = False

            if not skip:
                relevant_text.append(para_text)

        return " ".join(relevant_text)

    def extract_abbreviations(self, text: str) -> Counter[str]:
        """
        Extracts uppercase and mixed-case abbreviations from the text.
        Excludes pure Roman numerals, `exclude_terms`, words in quotes,
        and words that are 9 or more characters long and contain only letters.
        """
        doc_abbs: Counter[str] = Counter()

        # Remove quoted words
        text_no_quotes = re.compile(r'«\S+?»|\"[^\"]+\"').sub('', text)
        words = text_no_quotes.split()

        # Find words with at least 2 uppercase (Latin or Cyrillic) letters
        matches = [
            word for word in words
            if re.search(r'[A-ZА-ЯЁ].*[A-ZА-ЯЁ]', word)
        ]
        
        for match in matches:
            clean_match = self._clean_abbreviation(match)

            # Exclude pure Roman numerals and specific excluded terms,
            # and overly long abbreviations
            if (not self.roman_pattern.match(clean_match)
                and clean_match not in self.exclude_terms
                and not (len(clean_match) > 8 and clean_match.isalpha())
                ):
                doc_abbs[clean_match] += 1
        return doc_abbs

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
            window: int = 50,
            find_all: bool = True
        ) -> Union[str, List[str]]:
        """
        Finds and returns snippets of text around occurrences of the abbreviation.
        If `find_all` is False, returns the first occurrence; True returns all.
        """
        contexts: Set[str] = set()
        matches = re.finditer(
            rf'(?<!\w){re.escape(abbreviation)}(?!\w)', text
        )
        for match in matches:
            start = max(0, match.start() - window)
            end = min(len(text), match.end() + window)
            snippet = text[start:end]
            
            if find_all:
                contexts.add(snippet)
            else:
                return snippet
        return list(contexts)

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

class AbbreviationFormatter:
    """Class for formatting and cleaning abbreviation DataFrames."""
    
    # Greek to Latin letter mapping for descriptions formatting
    GREEK_TO_LATIN = {
        'α': 'A', 'β': 'B', 'γ': 'G', 'δ': 'D',
        'ε': 'E', 'ζ': 'Z', 'η': 'H', 'θ': 'TH',
        'ι': 'I', 'κ': 'K', 'λ': 'L', 'μ': 'M',
        'ν': 'N', 'ξ': 'X', 'ο': 'O', 'π': 'P',
        'ρ': 'R', 'σ': 'S', 'τ': 'T', 'υ': 'U',
        'φ': 'PH', 'χ': 'CH', 'ψ': 'PS', 'ω': 'O'
    }

    def format_description(self, row: Dict[str, str]) -> str:
        """
        Format the description by capitalizing words that correspond
        to abbreviation letters.
        """
        abbreviation: str = row['abbreviation']
        description: str = row['description']
        
        # Split description into English and Russian parts
        parts = description.split('(', 1)
        english_part = parts[0].strip().lower()
        russian_part = f"({parts[1]}" if len(parts) > 1 else ''
        
        # Convert abbreviation to uppercase Latin letters
        latin_abbr = ''.join(
            self.GREEK_TO_LATIN.get(char, char) for char in abbreviation
        ).upper()
        abbr_letters = ''.join(re.findall(r'[A-Z]', latin_abbr))
        
        english_part_capitalized = self._capitalize_by_abbreviation(
            english_part, abbr_letters
        )
        return f"{english_part_capitalized} {russian_part}".strip()

    def _capitalize_by_abbreviation(
            self, text: str, abbr_letters: str
        ) -> str:
        """
        Capitalize words in text based on abbreviation letters.
        """
        abbr_index = 0  # Position in the abbreviation
        text_pos = 0  # Position in the text
        text_chars = list(text)

        while abbr_index < len(abbr_letters) and text_pos < len(text_chars):
            current_char = text_chars[text_pos]
            if (current_char.lower() == abbr_letters[abbr_index].lower()
                and (text_pos == 0 or not text_chars[text_pos - 1].isalpha())):
                text_chars[text_pos] = current_char.upper()
                abbr_index += 1
            text_pos += 1
            
        return ''.join(text_chars)

    def clean_and_sort_abbreviations(
            self, abbreviations_df: DataFrame
        ) -> DataFrame:
        """
        Clean and sort abbreviations DataFrame:
        - Strips whitespace from all fields
        - Formats descriptions for abbreviations with English letters
        - Capitalizes first letters after digits
        - Removes duplicates
        - Sorts by abbreviation and description
        """
        # Create a copy to avoid modifying the original DataFrame
        df = abbreviations_df.copy()
        
        # Strip whitespace
        for column in ['abbreviation', 'description']:
            df[column] = df[column].astype(str).str.strip()

        # Format descriptions for entries with English letters
        english_mask = df['abbreviation'].str.contains(r'[A-Za-z]')
        formatted_descriptions = df[english_mask].apply(
            self.format_description, axis=1
        )
        df.loc[english_mask, 'description'] = formatted_descriptions

        # Capitalize first letter after digits
        df['description'] = df['description'].apply(self._capitalize_after_digits)

        # Remove duplicates and sort
        df = (df.drop_duplicates(subset=['abbreviation', 'description'])
              .sort_values(by=['abbreviation', 'description'])
              .reset_index(drop=True))
        
        return df

    def _capitalize_after_digits(self, text: str) -> str:
        """
        Capitalize the first letter following any leading digits.
        """
        return re.sub(
            r'^(\d*)([a-zA-ZА-Яа-яЁё])',
            lambda m: m.group(1) + m.group(2).upper(),
            text
        )

# -----------------------------------------------------------------------------
# Mistyped Abbreviation Checking
# -----------------------------------------------------------------------------

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

    def validate_abbreviation(self, abb: str, abb_dict: DataFrame) -> dict:
        """
        Validates an abbreviation for mixed characters.
        Checks for existing forms in the dictionary.
        Returns a dict with validation info.
        """
        has_cyr_chars = any(char in self.cyr2lat for char in abb)
        has_lat_chars = any(char in self.lat2cyr for char in abb)
        
        if not has_cyr_chars and not has_lat_chars:
            return {
                "original": abb,
                "highlighted": abb,
                "correct_form": None,
                "descriptions": []
            }

        possible_forms = self.generate_all_mixed_forms(abb)
        matched_rows = abb_dict[abb_dict['abbreviation'].isin(possible_forms)]
        
        if not matched_rows.empty:
            if len(matched_rows['abbreviation'].unique()) > 1:
                raise ValueError(
                    "[ERROR] Mixed-character abbreviations in the dictionary:"
                    f"\n{matched_rows}"
                )
            correct_form = matched_rows['abbreviation'].iloc[0]
            descriptions = list(matched_rows['description'].unique())
            highlighted = self.highlight_mismatch_characters(
                abb, correct_form
            )
        else:
            correct_form = None
            descriptions = []
            highlighted = self.highlight_mixed_characters(abb)

        return {
            "original": abb,
            "highlighted": highlighted,
            "correct_form": correct_form,
            "descriptions": descriptions
        }

    def generate_all_mixed_forms(self, abb: str) -> set:
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

    def highlight_mismatch_characters(
            self, user_abb: str, dict_abb: str
            ) -> str:
        """
        Compare each character and return a list of dictionaries
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
    
    def highlight_mixed_characters(self, abb: str) -> str:
        """Marks each character with its script type"""
        highlighted = []
        for ch in abb:
            if ch in self.cyr2lat:
                highlighted.append(f"{ch}(Cyr)")
            elif ch in self.lat2cyr:
                highlighted.append(f"{ch}(Lat)")
            else:
                highlighted.append(ch)
        return "".join(highlighted)

# -----------------------------------------------------------------------------
# Abbreviation comparison
# -----------------------------------------------------------------------------

def compare_abbreviations(
        new_abbs: DataFrame,
        old_abbs: DataFrame,
        compare_missing: bool = True,
        compare_new: bool = True
    ) -> Dict[str, DataFrame]:
    """
    Compare new and old abbreviation dictionaries.
    """
    results: Dict[str, DataFrame] = {}

    if compare_missing:
        not_in_new = old_abbs[
            ~old_abbs['abbreviation'].isin(new_abbs['abbreviation'])
        ]
        results['missing_abbs'] = not_in_new

    if compare_new:
        not_in_old = new_abbs[
            ~new_abbs['abbreviation'].isin(old_abbs['abbreviation'])
        ]
        results['new_found'] = not_in_old

    return results

# -----------------------------------------------------------------------------
# Output generation
# -----------------------------------------------------------------------------

class AbbreviationTableGenerator:
    """Class for generating formatted Word document tables with abbreviations."""

    def __init__(self):
        self.margins = {
            'top': 2.0,    # cm
            'bottom': 2.0, # cm
            'left': 3.0,   # cm
            'right': 1.5   # cm
        }
        self.first_column_width = 3.7  # cm
        self.font_name = 'Times New Roman'
        self.font_size = 12  # pt

    def _set_cell_border(self, cell: _Cell) -> None:
        """Set black borders on all four sides of the given cell."""
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        
        for edge in ("top", "bottom", "left", "right"):
            element = OxmlElement(f"w:{edge}")
            element.set(qn('w:val'), 'single')    # single line
            element.set(qn('w:sz'), '4')          # line size
            element.set(qn('w:color'), '000000')  # black color
            tcPr.append(element)

    def _format_paragraph_spacing(self, cell: _Cell) -> None:
        """Set line spacing to single and remove spacing before/after paragraphs."""
        for paragraph in cell.paragraphs:
            paragraph.paragraph_format.line_spacing = Pt(self.font_size)
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.space_before = Pt(0)

    def _format_cell_text(self, cell: _Cell, bold: bool = False) -> None:
        """Format text in the given cell with specified font and style."""
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.name = self.font_name
                run.font.size = Pt(self.font_size)
                run.font.bold = bold
                run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    def _format_cell(self, cell: _Cell, bold: bool = False) -> None:
        """Apply all formatting to a cell."""
        self._set_cell_border(cell)
        self._format_paragraph_spacing(cell)
        self._format_cell_text(cell, bold)

    def generate_document(self, matched_abbs: DataFrame) -> Document:
        """
        Generate a Word document with formatted abbreviation table.
        """
        doc = Document()

        # Set page margins
        for section in doc.sections:
            section.top_margin = Cm(self.margins['top'])
            section.bottom_margin = Cm(self.margins['bottom'])
            section.left_margin = Cm(self.margins['left'])
            section.right_margin = Cm(self.margins['right'])

            # Calculate second column width
            total_width = (
                section.page_width 
                - section.left_margin 
                - section.right_margin
            )
            self.second_column_width = total_width - Cm(self.first_column_width)

        # Create and format table
        table = self._create_table(doc, matched_abbs)
        self._set_column_widths(table)

        return doc

    def _create_table(self, doc: Document, data: DataFrame) -> Table:
        """Create and format table with header and data rows."""
        # Create table with header
        table = doc.add_table(rows=1, cols=2)
        header_cells = table.rows[0].cells
        
        # Set header text
        header_cells[0].text = 'Аббревиатура'
        header_cells[1].text = 'Расшифровка'

        # Format header cells
        for cell in header_cells:
            self._format_cell(cell, bold=True)

        # Add and format data rows
        for _, row_data in data.iterrows():
            row_cells = table.add_row().cells
            row_cells[0].text = row_data['abbreviation']
            row_cells[1].text = str(row_data['description'])

            for cell in row_cells:
                self._format_cell(cell, bold=False)

        return table

    def _set_column_widths(self, table: Table) -> None:
        """Set fixed widths for table columns."""
        for row in table.rows:
            row.cells[0].width = Cm(self.first_column_width)
            row.cells[1].width = self.second_column_width