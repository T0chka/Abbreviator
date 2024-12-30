import os
import re
import pandas as pd
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from extract_abbs import extract_abb_table, parse_table, get_all_abbreviations, compare_abbreviations

ABB_DICT_PATH = 'data/abb_dict.csv'
DOC_PATH = "C:/Workspace/R-pharm/work/abbreviation_app/data/docs_examples"
# input("Enter the path to the target document: ")

# formatting funs

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

# abbreviations extraction funs

def extract_abbreviations_from_doc(doc):
    """
    Extracts uppercase and mixed-case abbreviations from the document.
    Stops searching at "Список литературы" if the style is Heading1.
    Excludes pure Roman numerals, specific terms, and words in quotes.
    """
    doc_abbs = set()

    exclude_terms = {
        'ПРОТОКОЛ', 
        'КЛИНИЧЕСКОГО', 
        'ИССЛЕДОВАНИЯ'
    }
    pattern = re.compile(r'\b[а-яА-ЯёЁ]*[A-ZА-Я]{2,}(?:-[A-Z\d]{2,})*\b')
    roman_pattern = re.compile(r'^(?=[IVXLCDM])([IVXLCDM]+)(-[IVXLCDM]+)?[ABC]?$')
    quoted_pattern = re.compile(r'«([А-ЯЁ]+)»')
    stop_section = "Список литературы"

    for para in doc.paragraphs:
        if stop_section.lower() in para.text.lower() and para.style.name == 'Heading 1':
            break
        quoted_matches = quoted_pattern.findall(para.text)
        matches = pattern.findall(para.text)
        for match in matches:
            clean_match = match.strip('()')
            if (
                not roman_pattern.match(clean_match)
                and clean_match not in exclude_terms
                and clean_match not in quoted_matches
                ):
                doc_abbs.add(clean_match)
    return doc_abbs

def load_abbreviation_dict():
    """
    Load abbreviations from CSV, or return empty DataFrame if not found.
    """
    if os.path.exists(ABB_DICT_PATH):
        return pd.read_csv(ABB_DICT_PATH)
    return pd.DataFrame(columns=["abbreviation", "description"])

def find_abbreviation_in_context(doc, abbreviation, window=50):
    """
    Finds and returns a snippet of text around the first occurrence of the abbreviation.
    A window of characters before and after the abbreviation is shown.
    """
    for para in doc.paragraphs:
        match = re.search(rf'(\b{re.escape(abbreviation)}\b)', para.text)
        if match:
            start = max(0, match.start() - window)
            end = min(len(para.text), match.end() + window)
            return para.text[start:end]
    return None

def match_and_update_abbreviations(doc, doc_abbs, abb_dict):
    """
    Match doc abbreviations with dictionary, and prompt for new ones if needed.
    Also checks for any abbreviations from abb_dict that exist in the document but were not extracted.
    """

    # Match Abbreviations from CSV Dictionary
    matched_abbs = abb_dict[abb_dict['abbreviation'].isin(doc_abbs)]
    new_abbs = doc_abbs - set(matched_abbs['abbreviation'])

    # Check Full Text for Abbreviations from abb_dict
    found_text = " ".join(para.text for para in doc.paragraphs)
    for abb in abb_dict['abbreviation']:
        if re.search(rf'\b{re.escape(abb)}\b', found_text) and abb not in doc_abbs:
            matched_abbs = pd.concat([matched_abbs, abb_dict[abb_dict['abbreviation'] == abb]])

    # Prompt for Missing Abbreviations
    # if new_abbs:
    #     new_entries = []
    #     for abb in new_abbs:
    #         context = find_abbreviation_in_context(doc, abb)
    #         if context:
    #             print(f"\nFound in text: ...{context}...")
    #         desc = input(f"Enter description for '{abb}' (or press Enter to skip): ")
    #         if desc:
    #             new_entries.append({'abbreviation': abb, 'description': desc})

    #     # Update the abbreviation dictionary
    #     if new_entries:
    #         new_df = pd.DataFrame(new_entries)
    #         abb_dict = pd.concat([abb_dict, new_df], ignore_index=True).drop_duplicates()
    #         abb_dict.to_csv(ABB_DICT_PATH, index=False)
    #         print("Abbreviation list updated.")
    return matched_abbs

# output generation funs
def generate_abbreviation_table(matched_abbs):
    """
    Generates a .docx file with only a table,
    with page margins set to top/bottom=2cm, left=3cm, right=1.5cm,
    and a fixed 3.7cm width for the first column.
    """
    doc = Document()

    # Set page margins
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(3.0)
        section.right_margin = Cm(1.5)

        total_width = section.page_width - section.left_margin - section.right_margin
        second_col_width = total_width - Cm(3.7)

    # Create table with 1 header row, 2 columns
    table = doc.add_table(rows=1, cols=2)

    # Header
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Аббревиатура'
    hdr_cells[1].text = 'Расшифровка'

    # Format header cells
    for cell in hdr_cells:
        set_cell_border(cell)
        format_paragraph_spacing(cell)
        for run in cell.paragraphs[0].runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    # Fill table body
    for _, row_data in matched_abbs.iterrows():
        row_cells = table.add_row().cells
        row_cells[0].text = row_data['abbreviation']
        row_cells[1].text = str(row_data['description'])

        for cell in row_cells:
            set_cell_border(cell)
            format_paragraph_spacing(cell)
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                for run in paragraph.runs:
                    run.font.name = 'Times New Roman'
                    run.font.size = Pt(12)
                    run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    # Re-enforce width for the first column in all rows
    for row in table.rows:
        row.cells[0].width = Cm(3.7)
        row.cells[1].width = second_col_width

    # Save
    out_path = 'output/abbreviations_table.docx'
    os.makedirs('output', exist_ok=True)
    doc.save(out_path)
    print(f"Abbreviation table saved to {out_path}")

if __name__ == "__main__":
    doc_file = [f for f in os.listdir(DOC_PATH) if f.endswith('.docx')]
    if len(doc_file) != 1:
        raise FileNotFoundError("Expected exactly one .docx file in the folder.")
    
    doc_path = os.path.join(DOC_PATH, doc_file[0])
    print(f"[INFO] Processing document: {doc_path}")

    doc = Document(doc_path)
    doc_abbs = extract_abbreviations_from_doc(doc)
    abb_dict = load_abbreviation_dict()
    matched_abbs = match_and_update_abbreviations(doc, doc_abbs, abb_dict)
    generate_abbreviation_table(matched_abbs)

    initial_abbs = get_all_abbreviations(DOC_PATH)
    compare_abbreviations(old_abbs=initial_abbs, new_abbs=matched_abbs)