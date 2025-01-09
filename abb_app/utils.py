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

NAMESPACE = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

# -----------------------------------------------------------------------------
# Text, abbreviation, and context extraction
# -----------------------------------------------------------------------------

def load_abbreviation_dict() -> DataFrame:
    """
    Load abbreviations from CSV, or return empty DataFrame if not found.
    """
    if os.path.exists(ABB_DICT_PATH):
        return pd.read_csv(ABB_DICT_PATH)
    return pd.DataFrame(columns=["abbreviation", "description"])

def extract_relevant_text(
        doc: Document,
        skip_sections: List[str] = SKIP_SECTIONS
        ) -> str:
    """
    Extracts text from the document, excluding sections like "СПИСОК ЛИТЕРАТУРЫ".
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

        if any(t.upper() in para_text.upper() for t in skip_sections):
            print(
                f"[extract_relevant_text] Detected: {para_text[:100]} - "
                f"Style: {para.style.name} - "
                f"Is Bold: {is_bold} - Is Heading: {is_heading}"
            )
        if ((is_bold or is_heading)
            and any(t.upper() in para_text.upper() for t in skip_sections)
            ):
            print("[extract_relevant_text] Skipping this section")
            skip = True

        elif (is_bold or is_heading) and skip:
            print(
                f"\n[extract_relevant_text] Resuming search at section: {para_text}"
            )
            skip = False

        if not skip:
            relevant_text.append(para_text)

    return " ".join(relevant_text)

def extract_abbs_from_text(
    text: str,
    exclude_terms: Set[str] = EXCLUDE_TERMS
) -> Counter[str]:
    """
    Extracts uppercase and mixed-case abbreviations from the document.
    Stops searching at "Список литературы" if the style is Heading 1.
    Excludes pure Roman numerals, specific terms, and words in quotes,
    and abbs that are 9 or more characters long and contain only letters.
    """
    doc_abbs: Counter[str] = Counter()

    roman_pattern = re.compile(
        r'^(?:[IVXLCDM]+(?:-[IVXLCDM]+)?)[A-Za-zА-Яа-яёЁ]*$',
        re.IGNORECASE
    )
    # Remove quoted words
    text_no_quotes = re.compile(r'«\S+?»|\"[^\"]+\"').sub('', text)
    words = text_no_quotes.split()

    # Find words with at least 2 uppercase (Latin or Cyrillic) letters
    matches = [
        word for word in words
        if re.search(r'[A-ZА-ЯЁ].*[A-ZА-ЯЁ]', word)
    ]
    
    for match in matches:
        clean_match = match.strip(':;,.»«][')

        # Remove '(' if at the beginning and ')' if unmatched
        if clean_match.startswith('('):
            clean_match = clean_match[1:]
        if clean_match.endswith(')') and clean_match.count('(') == 0:
            clean_match = re.sub(r'\)+$', '', clean_match)
        
        clean_match = clean_match.strip('»«][')

        # Exclude pure Roman numerals and specific excluded terms,
        # and overly long abbreviations
        if (not roman_pattern.match(clean_match)
            and clean_match not in exclude_terms
            and not (len(clean_match) > 8 and clean_match.isalpha())
            ):
            doc_abbs[clean_match] += 1
    return doc_abbs

def find_abbreviation_context(
    text: str,
    abbreviation: str,
    window: int = 50,
    find_all: bool = False
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

def separate_abbs(
    doc_abbs: Counter[str],
    abb_dict: DataFrame,
    text: str
) -> Tuple[DataFrame, List[Dict[str, Union[str, List[str]]]]]:
    """
    Separate abbreviations into matched and new ones.
    """
    freq_abbs: Dict[str, int] = {
        abb: count for abb, count in doc_abbs.items() if count > 1
    }
    matched_abbs = abb_dict[abb_dict['abbreviation'].isin(freq_abbs)].copy()
    new_abbs = set(freq_abbs) - set(matched_abbs['abbreviation'])

    return matched_abbs, [
        {
            'abbreviation': abb,
            'contexts': find_abbreviation_context(text, abb, find_all=True)
        }
        for abb in new_abbs
    ]

# -----------------------------------------------------------------------------
# Abbreviation table extraction
# -----------------------------------------------------------------------------

def extract_abb_table(
    doc: Document,
    section_patterns: List[str] = SECTION_PATTERNS
) -> Optional[CT_Tbl]:
    """
    Extract the first relevant table from the document. If the document contains
    a section matching `section_pattern`, extract the first table after it,
    if it consists of a single table (without section headings),
    extract the first table directly.
    """
    # If the entire doc is just one table, return it
    tables: List[CT_Tbl] = [
        block for block in doc.element.body 
        if block.tag.endswith('tbl')
    ]
    if len(tables) == 1:
        return tables[0]
    
    found_section = False

    for block in doc.element.body:
        if block.tag.endswith('p'):
            para_text = ''.join(
                node.text for node in block.findall(
                    './/w:t', namespaces=NAMESPACE
                ) if node.text
            )
            if any(pattern.casefold() in para_text.casefold() 
                  for pattern in section_patterns):
                
                # Must NOT end with a digit (avoid missformated ToC)
                if para_text.strip().endswith(tuple("0123456789")):
                    continue
                # Must NOT have a hyperlink (avoid ToC lines)
                if block.find('.//w:hyperlink', namespaces=NAMESPACE) is not None:
                    continue
                # Must have some heading indication (pStyle or outlineLvl)
                para_style = block.find('.//w:pStyle', namespaces=NAMESPACE)
                outline_level = block.find('.//w:outlineLvl', namespaces=NAMESPACE)

                if para_style is not None or outline_level is not None:
                    found_section = True
                    continue

        if found_section and block.tag.endswith('tbl'):
            return block

    return None

def parse_table(table_element: CT_Tbl) -> Optional[DataFrame]:
    """
    Given an lxml table element, return a DataFrame. 
    Assumes the table has two columns: [abbreviation, description].
    """
    rows_data: List[List[str]] = []
    first_row = True

    for row in table_element.findall('.//w:tr', namespaces=NAMESPACE):
        cell_texts = []
        for cell in row.findall('.//w:tc', namespaces=NAMESPACE):
            texts = cell.findall('.//w:t', namespaces=NAMESPACE)
            cell_text = ''.join(t.text for t in texts if t.text)
            cell_texts.append(cell_text.strip())

        if first_row and cell_texts[:2] == ["Аббревиатура", "Расшифровка"]:
            first_row = False
            continue

        rows_data.append(cell_texts)

    df = pd.DataFrame(rows_data)
    if df.shape[1] == 2:
        df.columns = ['abbreviation', 'description']
        return df
    
def get_init_abb_table(
        file_path: str,
        section_patterns: List[str] = SECTION_PATTERNS
        ) -> DataFrame:
    """
    Extract the relevant table from the doc, parse it, and store
    in a single DataFrame with columns ['abbreviation', 'description'].
    """
    doc = Document(os.path.abspath(file_path))
    table_element = extract_abb_table(doc, section_patterns)    
    if table_element is None:
        print(f"[INFO] No relevant abbreviation table found in: {file_path}")
        return pd.DataFrame(columns=['abbreviation', 'description'])

    df = parse_table(table_element)
    if df is not None and not df.empty:
        clean_and_sort_abbreviations(df)
    else:
        print(f"[WARNING] Table structure error or empty table in: {file_path}")
    return df
    
# -----------------------------------------------------------------------------
# Abbreviation dictionary formatting
# -----------------------------------------------------------------------------

def format_abbreviation(row: Dict[str, str]) -> str:
    """
    Format the 'description' so that each word whose first letter
    matches the *next* letter in 'abbreviation' is capitalized
    (in sequence, left to right).
    """
    abbr: str = row['abbreviation']
    desc: str = row['description']
    
    # Split out any part part in first parentheses, if present
    parts = desc.split('(', 1)
    english_desc = parts[0].strip().lower()
    russian_desc = '(' + parts[1] if len(parts) > 1 else ''
    
    # Convert abbreviation (with Greek letters) to uppercase Latin letters
    greek_to_latin = {
        'α': 'A', 'β': 'B', 'γ': 'G', 'δ': 'D',
        'ε': 'E', 'ζ': 'Z', 'η': 'H', 'θ': 'TH',
        'ι': 'I', 'κ': 'K', 'λ': 'L', 'μ': 'M',
        'ν': 'N', 'ξ': 'X', 'ο': 'O', 'π': 'P',
        'ρ': 'R', 'σ': 'S', 'τ': 'T', 'υ': 'U',
        'φ': 'PH', 'χ': 'CH', 'ψ': 'PS', 'ω': 'O'
    }
    abbr = ''.join(greek_to_latin.get(char, char) for char in abbr).upper()
    abbr_letters = ''.join(re.findall(r'[A-Z]', abbr))
    
    def capitalize_by_abbreviation(english_desc, abbr_letters):
        abbr_idx = 0 # position in the abbreviation
        pos = 0      # position in the description
        desc_list = list(english_desc)

        while abbr_idx < len(abbr_letters) and pos < len(desc_list):
            if (desc_list[pos].lower() == abbr_letters[abbr_idx].lower()
                    and (pos == 0 or not desc_list[pos - 1].isalpha())):
                desc_list[pos] = desc_list[pos].upper()
                abbr_idx += 1
            pos += 1
        return ''.join(desc_list)
    
    english_desc_cap = capitalize_by_abbreviation(english_desc, abbr_letters)
    desc = f"{english_desc_cap} {russian_desc}".strip()
    return desc

def clean_and_sort_abbreviations(abb_dict: DataFrame) -> None:
    """
    Cleans, deduplicates, and sorts the abbreviation DataFrame in place.
    - Strips whitespace from 'abbreviation' and 'description'.
    - Capitalizes words in 'description' using format_abbreviation().
    - Removes duplicates.
    - Sorts by ['abbreviation', 'description'].
    - Resets the index.
    """
    for col in ['abbreviation', 'description']:
        abb_dict.loc[:, col] = abb_dict[col].astype(str).str.strip()

    # Apply format_abbreviation only if abbreviation contains English letters
    mask = abb_dict['abbreviation'].str.contains(r'[A-Za-z]')
    formatted = abb_dict.loc[mask].apply(format_abbreviation, axis=1)
    abb_dict.loc[mask, 'description'] = formatted.values

    # Capitalize the first letter after any leading digits (if present)
    for i in abb_dict.index:
        value = abb_dict.at[i, 'description']
        abb_dict.at[i, 'description'] = re.sub(
            r'^(\d*)([a-zA-ZА-Яа-яЁё])',
            lambda m: m.group(1) + m.group(2).upper(),
            value
        )
    abb_dict.drop_duplicates(
        subset=['abbreviation', 'description'],
        inplace=True
    )
    abb_dict.sort_values(
        by=['abbreviation', 'description'],
        inplace=True, ignore_index=True
    )
    abb_dict.reset_index(drop=True, inplace=True)

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

def set_cell_border(cell: _Cell) -> None:
    """
    Sets black borders on all four sides of the given cell.
    """
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for edge in ("top", "bottom", "left", "right"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn('w:val'), 'single')    # single line
        element.set(qn('w:sz'), '4')          # line size
        element.set(qn('w:color'), '000000')  # black color
        tcPr.append(element)

def format_paragraph_spacing(cell: _Cell) -> None:
    """
    Sets line spacing to single and spacing after to 0 for paragraphs in a cell.
    """
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.line_spacing = Pt(12)  # Single line spacing
        paragraph.paragraph_format.space_after = Pt(0)    # No space after paragraph
        paragraph.paragraph_format.space_before = Pt(0)   # No space before paragraph

def format_cell_text(cell: _Cell, bold: bool = False) -> None:
    """
    Formats text in the given cell with specified font and style.
    """
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)
            run.font.bold = bold
            run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
            
def generate_abbreviation_table(matched_abbs: DataFrame) -> Document:
    """
    Generates a .docx file with only a table,
    with page margins set to top/bottom=2cm, left=3cm, right=1.5cm,
    and a fixed 3.7cm width for the first column.
    Returns the Document object instead of saving it.
    """
    doc: Document = Document()

    # Set page margins
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(3.0)
        section.right_margin = Cm(1.5)

        total_width = (
            section.page_width - section.left_margin - section.right_margin
        )
        second_col_width = total_width - Cm(3.7)

    # Create table (header row + body, 2 columns)
    table = doc.add_table(rows=1, cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Аббревиатура'
    hdr_cells[1].text = 'Расшифровка'

    # Format header
    for cell in hdr_cells:
        set_cell_border(cell)
        format_paragraph_spacing(cell)
        format_cell_text(cell, bold=True)

    # Table body
    for _, row_data in matched_abbs.iterrows():
        row_cells = table.add_row().cells
        row_cells[0].text = row_data['abbreviation']
        row_cells[1].text = str(row_data['description'])

        for cell in row_cells:
            set_cell_border(cell)
            format_paragraph_spacing(cell)
            format_cell_text(cell, bold=False)

    # Enforce column widths
    for row in table.rows:
        row.cells[0].width = Cm(3.7)
        row.cells[1].width = second_col_width

    return doc
