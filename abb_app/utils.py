import os
import re
import pandas as pd
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from thefuzz import process, fuzz
from collections import Counter

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
    'КОНТРОЛЬ', 'ТЕРМИНОВ', 'ЗАПИСЕЙ', 'ГИПОТЕЗА', 'ДАННЫМИ',
    'ДАННЫМ/ДОКУМЕНТАЦИИ'
}

NAMESPACE = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

# -----------------------------------------------------------------------------
# Text, abbreviation, and context extraction
# -----------------------------------------------------------------------------

def load_abbreviation_dict():
    """
    Load abbreviations from CSV, or return empty DataFrame if not found.
    """
    if os.path.exists(ABB_DICT_PATH):
        return pd.read_csv(ABB_DICT_PATH)
    return pd.DataFrame(columns=["abbreviation", "description"])

def extract_relevant_text(doc, skip_sections=SKIP_SECTIONS):
    """
    Extracts text from the document, excluding sections like "СПИСОК ЛИТЕРАТУРЫ".
    The exclusion starts at the section title in bold or heading style
    and resumes at the next bold or heading section.
    """
    relevant_text = []
    skip = False

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
                f"[DEBUG] Detected: {para_text} - "
                f"Style: {para.style.name} - "
                f"Is Bold: {is_bold} - Is Heading: {is_heading}"
            )
        if ((is_bold or is_heading)
            and any(t.upper() in para_text.upper() for t in skip_sections)
            ):
            print("[DEBUG] Skipping this section")
            skip = True

        elif (is_bold or is_heading) and skip:
            print(
                f"[DEBUG] Resuming search at section: {para_text}"
            )
            skip = False

        if not skip:
            relevant_text.append(para_text)

    return " ".join(relevant_text)

def extract_abbs_from_text(text:str, exclude_terms=EXCLUDE_TERMS)->Counter:
    """
    Extracts uppercase and mixed-case abbreviations from the document.
    Stops searching at "Список литературы" if the style is Heading 1.
    Excludes pure Roman numerals, specific terms, and words in quotes,
    and abbs that are 9 or more characters long and contain only letters.
    """
    doc_abbs = Counter()

    roman_pattern = re.compile(
        r'^(?:[IVXLCDM]+(?:-[IVXLCDM]+)?)[A-Za-zА-Яа-яёЁ]*$',
        re.IGNORECASE
    )
    # Remove quoted words
    text_no_quotes = re.compile(r'«\S+»').sub('', text)
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

def find_abbreviation_context(text, abbreviation, window=50, find_all=False):
    """
    Finds and returns snippets of text around occurrences of the abbreviation.
    If `find_all` is False, returns the first occurrence; True returns all.
    """
    contexts = set()
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

def separate_abbs(doc_abbs, abb_dict, text):
    """
    Separate abbreviations into matched and new ones.
    """
    freq_abbs = {abb: count for abb, count in doc_abbs.items() if count > 1}
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

def extract_abb_table(doc, section_patterns=SECTION_PATTERNS):
    """
    Extract the first relevant table from the document.
    - If the document contains a section matching `section_pattern`, extract the first table after it.
    - If the document consists of a single table (without section headings), extract the first table directly.
    """
    # If the entire doc is just one table, return it
    tables = [block for block in doc.element.body if block.tag.endswith('tbl')]
    if len(tables) == 1:
        return tables[0]
    
    found_section = False

    for block in doc.element.body:
        if block.tag.endswith('p'):
            para_text = ''.join(
                node.text for node in block.findall('.//w:t', namespaces=NAMESPACE) if node.text
            )
            if any(pattern.casefold() in para_text.casefold() for pattern in section_patterns):
                
                # Must NOT end with a digit (avoid "СПИСОК СОКРАЩЕНИЙ<page number>" in missformated ToC)
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

def parse_table(table_element):
    """
    Given an lxml table element, return a DataFrame. 
    Assumes the table has two columns: [abbreviation, description].
    """
    rows_data = []
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
    
def get_init_abb_table(file_path, section_patterns=SECTION_PATTERNS):
    """
    Extract the relevant table from the doc, parse it,
    and store in a single DataFrame with columns ['abbreviation', 'description'].
    """
    if not file_path.endswith('.docx'):
        raise ValueError(f"Invalid file type: {file_path}. Expected a .docx file.")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    doc = Document(file_path)
    table_element = extract_abb_table(doc, section_patterns)
    
    if table_element is None:
        print(f"[INFO] No relevant abbreviation table found in: {file_path}")
        return df

    df = parse_table(table_element)
    if df is not None and not df.empty:
        clean_and_sort_abbreviations(df)
    else:
        print(f"[WARNING] Table structure error or empty table in: {file_path}")
    return df
    
# -----------------------------------------------------------------------------
# Abbreviation dictionary formatting
# -----------------------------------------------------------------------------

def format_abbreviation(row):
    """
    Format the 'description' so that each word whose first letter
    matches the *next* letter in 'abbreviation' is capitalized
    (in sequence, left to right).
    """
    abbr = row['abbreviation']
    desc = row['description']
    
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
            if (desc_list[pos].lower() == abbr_letters[abbr_idx].lower() and
                (pos == 0 or not desc_list[pos - 1].isalpha())):
                desc_list[pos] = desc_list[pos].upper()
                abbr_idx += 1
            pos += 1
        return ''.join(desc_list)
    
    english_desc_cap = capitalize_by_abbreviation(english_desc, abbr_letters)
    # Reconstruct the description (capitalize English part + Russian part if present)
    desc = f"{english_desc_cap} {russian_desc}".strip()
    return desc

def clean_and_sort_abbreviations(abb_dict):
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
    abb_dict.drop_duplicates(subset=['abbreviation', 'description'], inplace=True)
    abb_dict.sort_values(by=['abbreviation', 'description'], inplace=True, ignore_index=True)
    abb_dict.reset_index(drop=True, inplace=True)


# -----------------------------------------------------------------------------
# Abbreviation comparison
# -----------------------------------------------------------------------------

def compare_abbreviations(new_abbs, old_abbs, compare_missing=True, compare_new=True):
    results = {}

    if compare_missing:
        not_in_new = old_abbs[~old_abbs['abbreviation'].isin(new_abbs['abbreviation'])]
        results['missing_abbs'] = not_in_new
        print(f"\n[INFO] Abbreviations in the old_abbs that are NOT in the new_abbs: {len(not_in_new)}")
        print(not_in_new)

    if compare_new:
        not_in_old = new_abbs[~new_abbs['abbreviation'].isin(old_abbs['abbreviation'])]
        results['new_found'] = not_in_old
        print(f"\n[INFO] Abbreviations in the new_abbs that are NOT in the old_abbs: {len(not_in_old)}")
        print(not_in_old)

    return results

# -----------------------------------------------------------------------------
# Output generation
# -----------------------------------------------------------------------------

def set_cell_border(cell):
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

def format_paragraph_spacing(cell):
    """
    Sets line spacing to single and spacing after to 0 for paragraphs in a cell.
    """
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.line_spacing = Pt(12)  # Single line spacing
        paragraph.paragraph_format.space_after = Pt(0)    # No space after paragraph
        paragraph.paragraph_format.space_before = Pt(0)   # No space before paragraph

def format_cell_text(cell, bold=False):
    """
    Formats text in the given cell with specified font and style.
    """
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)
            run.font.bold = bold
            run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
            
def generate_abbreviation_table(matched_abbs):
    """
    Generates a .docx file with only a table,
    with page margins set to top/bottom=2cm, left=3cm, right=1.5cm,
    and a fixed 3.7cm width for the first column.
    Returns the Document object instead of saving it.
    """
    doc = Document()

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