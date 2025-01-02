import os
import re
import pandas as pd
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Local imports
from extract_abbs import (
    get_all_abbreviations,
    compare_abbreviations,
    clean_and_sort_abbreviations
)
from format_abbs import clean_and_sort_abbreviations

ABB_DICT_PATH = 'data/abb_dict.csv'
DOC_PATH = "C:/Workspace/R-pharm/work/abbreviation_app/data/docs_examples"

# ------------------------------
# Abbreviations and context extraction
# ------------------------------

def load_abbreviation_dict():
    """
    Load abbreviations from CSV, or return empty DataFrame if not found.
    """
    if os.path.exists(ABB_DICT_PATH):
        return pd.read_csv(ABB_DICT_PATH)
    return pd.DataFrame(columns=["abbreviation", "description"])

def extract_abbreviations_from_doc(doc):
    """
    Extracts uppercase and mixed-case abbreviations from the document.
    Stops searching at "Список литературы" if the style is Heading 1.
    Excludes pure Roman numerals, specific terms, and words in quotes.
    """
    doc_abbs = set()

    exclude_terms = {
        'ПРОТОКОЛ', 
        'КЛИНИЧЕСКОГО', 
        'ИССЛЕДОВАНИЯ'
    }
    roman_pattern = re.compile(r'^(?:[IVXLCDM]+(?:-[IVXLCDM]+)?)[A-Za-zА-Яа-яёЁ]*$', re.IGNORECASE)
    stop_section = "Список литературы"

    for para in doc.paragraphs:
        # Stop if we see "Список литературы" in a Heading 1 paragraph
        if stop_section.lower() in para.text.lower() and para.style.name == 'Heading 1':
            break

        # Remove quoted words like «something» from consideration
        text_no_space_quoted = re.compile(r'«\S+»').sub('', para.text)
        words = text_no_space_quoted.split()
        
        # Find words with at least 2 uppercase (Latin or Cyrillic) letters
        matches = [word for word in words if re.search(r'[A-ZА-ЯЁ].*[A-ZА-ЯЁ]', word)]
        
        for match in matches:
            clean_match = match.strip(':;,.»«][')

            # Remove '(' if at the beginning and trailing ')' only if there is no '(' in the remaining word
            # E.g. (ABC) -> ABC, but AUC(0-24) remains with parentheses
            if clean_match.startswith('('):
                clean_match = clean_match[1:]
            if clean_match.endswith(')') and clean_match.count('(') == 0:
                clean_match = re.sub(r'\)+$', '', clean_match)
            
            clean_match = clean_match.strip('»«][')

            # Exclude pure Roman numerals, excluded terms, etc.
            if (
                not roman_pattern.match(clean_match)
                and clean_match not in exclude_terms
                ):
                doc_abbs.add(clean_match)
    return doc_abbs

def find_abbreviation_context(doc, abbreviation, window=50, find_all=False):
    """
    Finds and returns snippets of text around occurrences of the abbreviation.
    If `find_all` is False, returns the first occurrence; True returns all.
    """
    contexts = set()    
    for para in doc.paragraphs:
        matches = re.finditer(rf'(?<!\w){re.escape(abbreviation)}(?!\w)', para.text)
        
        for match in matches:
            start = max(0, match.start() - window)
            end = min(len(para.text), match.end() + window)
            snippet = para.text[start:end]
            
            if find_all:
                contexts.add(snippet)
            else:
                return snippet
    
    return list(contexts) if find_all else None

# -------------------------------------------------------------------
# Mistyped Abbreviation Checking
# -------------------------------------------------------------------

def generate_all_mixed_forms(abb, cyr2lat, lat2cyr):
    """
    Given an abbreviation that may have mixed Cyrillic/Latin chars,
    generate all possible "conversion" permutations by:
      - leaving the character as is,
      - converting Cyrillic -> Latin,
      - converting Latin -> Cyrillic.
    """
    results = set()

    def backtrack(i, current):
        if i == len(abb):
            results.add("".join(current))
            return

        ch = abb[i]
        # 1) Leave the character as is
        current.append(ch)
        backtrack(i + 1, current)
        current.pop()

        # 2) Cyrillic -> Latin (if ch is in cyr2lat)
        if ch in cyr2lat:
            current.append(cyr2lat[ch])
            backtrack(i + 1, current)
            current.pop()

        # 3) Latin -> Cyrillic (if ch is in lat2cyr)
        if ch in lat2cyr:
            current.append(lat2cyr[ch])
            backtrack(i + 1, current)
            current.pop()

    backtrack(0, [])
    return results

def highlight_mixed_characters(abb, cyr2lat, lat2cyr):
    """
    Returns a debug-friendly string, highlighting each character from the dicts
    cyr2lat and lat2cyr with (Cyr) or (Lat).
    """
    highlighted_chars = []
    for ch in abb:
        if ch in cyr2lat:
            highlighted_chars.append(f"{ch}(Cyr)")
        elif ch in lat2cyr:
            highlighted_chars.append(f"{ch}(Lat)")
        else:
            highlighted_chars.append(ch)
    return "".join(highlighted_chars)

def check_and_correct_misstyped_abb(abb, abb_dict):
    """
    Detect if `abb` is a mixed-type (Cyr/Lat). If so, suggest
    one or more possible corrections from existing `abb_dict`.
    Returns the corrected abbreviation or the original if user skips.
    """
    # Map for character-by-character conversion
    cyr2lat = {
        'А': 'A',  # Cyrillic А -> Latin A
        'В': 'B',  # Cyrillic В -> Latin B
        'С': 'C',  # Cyrillic С -> Latin C
        'Е': 'E',  # Cyrillic Е -> Latin E
        'Н': 'H',  # Cyrillic Н -> Latin H
        'К': 'K',  # Cyrillic К -> Latin K
        'М': 'M',  # Cyrillic М -> Latin M
        'О': 'O',  # Cyrillic О -> Latin O
        'Р': 'P',  # Cyrillic Р -> Latin P
        'Т': 'T',  # Cyrillic Т -> Latin T
        'У': 'Y',  # Cyrillic У -> Latin Y
        'Х': 'X'   # Cyrillic Х -> Latin X
    }
    lat2cyr = {v: k for k, v in cyr2lat.items()}

    is_mixed = any(char in cyr2lat for char in abb) and any(char in lat2cyr for char in abb)
    possible_forms = generate_all_mixed_forms(abb, cyr2lat, lat2cyr)
    abb_hl = highlight_mixed_characters(abb, cyr2lat, lat2cyr)

    matches = []

    # Check which generated forms already exist in abb_dict
    for form in possible_forms:
        row = abb_dict[abb_dict['abbreviation'] == form]
        if not row.empty:
            desc = row['description'].values[0]
            matches.append((form, desc))

    # No matches found; just return original
    if not matches and is_mixed:
        print(f"\n[INFO] No corrections found for mixed-language abbreviation: '{abb_hl}'")
        print("[INFO] This may be a new abbreviation or mistyped. Consider adding it manually.")
        return abb
    
    # De-duplicate the matches
    matches = list(dict.fromkeys(matches))

    # If exactly 1 match, ask user to confirm
    if len(matches) == 1:
        corrected_abb, description = matches[0]
        corrected_abb_hl = highlight_mixed_characters(corrected_abb, cyr2lat, lat2cyr)
        print(f"\n[WARNING] '{abb_hl}' appears mistyped.")
        print(f"Did you mean '{corrected_abb_hl}'? - {description}")

        choice = input(f"Use '{corrected_abb}' instead of '{abb}'? (y/n): ").strip().lower()
        return corrected_abb if choice == 'y' else abb

    # If multiple matches, prompt user to pick
    if matches:
        print(f"\n[WARNING] '{abb_hl}' appears mistyped. Possible corrections:")
        for i, (corr, desc) in enumerate(matches, start=1):
            print(f" {i}. {corr} - {desc}")

        choice = input(f"Select the correct abbreviation for '{abb}' (1-{len(matches)}) or Enter to skip: ").strip()
        if choice.isdigit():
            if 1 <= int(choice) <= len(matches):
                corrected_abb, _ = matches[int(choice) - 1]
                confirm = input(f"Use '{corrected_abb}' instead of '{abb}'? (y/n): ").strip().lower()
                if confirm == 'y':
                    return corrected_abb

    return abb

# -------------------------------------------------------------------
# Custom description input
# -------------------------------------------------------------------

def get_custom_description(abb, abb_dict, matched_abbs):
    """
    Prompts the user to enter a custom description for a given abbreviation.
    Updates abb_dict and matched_abbs with the new description.
    """
    custom_desc = input(f"Enter custom description for '{abb}': ").strip()
    
    if custom_desc:
        new_entry = pd.DataFrame([{'abbreviation': abb, 'description': custom_desc}])
        
        # Check if the description already exists for another abbreviation
        existing_desc = abb_dict[abb_dict['description'] == custom_desc]
        
        if not existing_desc.empty:
            existing_abbs = ", ".join(existing_desc['abbreviation'].unique())
            print(
                f"[INFO] This description already exists for '{existing_abbs}'. "
                f"Linking '{abb}' to the existing description."
            )
            matched_abbs = matched_abbs[
                (matched_abbs['abbreviation'] != abb) |
                (matched_abbs['description'] == custom_desc)
            ]
        else:
            abb_dict = pd.concat([abb_dict, new_entry], ignore_index=True)
            abb_dict = clean_and_sort_abbreviations(abb_dict)
            matched_abbs = pd.concat([matched_abbs, new_entry], ignore_index=True)
            print(f"[INFO] New description for '{abb}' added to abbreviation dictionary.")
    else:
        print(f"[INFO] No custom description provided. '{abb}' will be excluded.")
    
    return matched_abbs, abb_dict

# -------------------------------------------------------------------
# Handling Multiple Descriptions
# -------------------------------------------------------------------

def handle_multiple_descriptions(abb, descriptions, abb_dict, matched_abbs, doc):
    """
    Let user pick or create a new description if multiple exist.
    Returns updated (matched_abbs, abb_dict).
    """
    print(f"\nMultiple descriptions found for '{abb}':")
    for i, desc in enumerate(descriptions, 1):
        print(f"{i}. {desc}")

    contexts = find_abbreviation_context(doc, abb, find_all=True)
    for context in contexts:
        print(f"   Context: ...{context}...")        

    print("0. Enter a custom description")
    while True:
        choice = input(f"Select the correct description for '{abb}' (1-{len(descriptions)}) or 0 to add custom: ")
        if choice == "0":
            custom_desc = input(f"Enter custom description for '{abb}': ").strip()
            if custom_desc:
                new_entry = pd.DataFrame([{'abbreviation': abb, 'description': custom_desc}])
                
                # Check if the description already exists for another abbreviation
                existing_desc = abb_dict[abb_dict['description'] == custom_desc]
                
                if not existing_desc.empty:
                    existing_abbs = ", ".join(existing_desc['abbreviation'].unique())
                    print(
                        f"[INFO] This description already exists for '{existing_abbs}'. "
                        f"Linking '{abb}' to the existing description."
                    )
                    matched_abbs = matched_abbs[
                        (matched_abbs['abbreviation'] != abb) |
                        (matched_abbs['description'] == custom_desc)
                    ]
                else:
                    abb_dict = pd.concat([abb_dict, new_entry], ignore_index=True)
                    abb_dict = clean_and_sort_abbreviations(abb_dict)
                    print(f"[INFO] New description for '{abb}' added to abbreviation dictionary.")
                    
                    matched_abbs = pd.concat([matched_abbs, new_entry], ignore_index=True)
            break
        
        elif choice.isdigit() and 1 <= int(choice) <= len(descriptions):
            chosen_desc = descriptions[int(choice) - 1]
            matched_abbs = matched_abbs[
                (matched_abbs['abbreviation'] != abb) |
                (matched_abbs['description'] == chosen_desc)
            ]
            break
        else:
            print("[WARNING] Invalid choice. Please try again.")

    return matched_abbs, abb_dict

# -------------------------------------------------------------------
# Core Logic: match and update abbreviations
# -------------------------------------------------------------------

def match_and_update_abbreviations(doc, doc_abbs, abb_dict):
    """
    Match abbreviations found in the doc with an existing dictionary, 
    prompting for new or custom descriptions as needed.
    Also updates abb_dict with new entries.
    """
    # 1) Abbreviations that already exist in the dictionary
    matched_abbs = abb_dict[abb_dict['abbreviation'].isin(doc_abbs)]
    new_abbs = doc_abbs - set(matched_abbs['abbreviation'])

    # Handle existing abbreviations with multiple descriptions
    for abb in matched_abbs['abbreviation'].unique():
        descriptions = abb_dict.loc[abb_dict['abbreviation'] == abb, 'description'].unique()
    
        if len(descriptions) > 1:
            matched_abbs, abb_dict = handle_multiple_descriptions(
                abb, descriptions, abb_dict, matched_abbs, doc
            )
    
    # 2) Prompt for new abbreviations not in dict
    if new_abbs:
        new_entries = []
        for abb in new_abbs:

            # Check for possible mistypes
            corrected_abb = check_and_correct_misstyped_abb(abb, abb_dict)
            
            # If corrected_abb exists, skip new description prompt
            if corrected_abb in abb_dict['abbreviation'].values:
                rows_for_corrected = abb_dict[abb_dict['abbreviation'] == corrected_abb]
                matched_abbs = pd.concat([matched_abbs, rows_for_corrected], ignore_index=True)

                # If multiple descriptions exist for the corrected abbreviation
                descriptions = rows_for_corrected['description'].unique()    
                if len(descriptions) > 1:
                    matched_abbs, abb_dict = handle_multiple_descriptions(
                        corrected_abb, descriptions, abb_dict, matched_abbs, doc
                    )
                continue
            
            # Otherwise, prompt user for a description
            contexts = find_abbreviation_context(doc, abb, find_all=True)
            print(f"\nFound '{abb}' in text:")
            for context in contexts:
                print(f"...{context}...")
            desc = input(f"Enter description for '{abb}' (or press Enter to skip): ").strip()
            if desc:
                new_entries.append({'abbreviation': abb, 'description': desc})

        # Add newly provided abbreviations
        if new_entries:
            new_df = pd.DataFrame(new_entries)
            matched_abbs = pd.concat([matched_abbs, new_df], ignore_index=True)
            abb_dict = pd.concat([abb_dict, new_df], ignore_index=True)
            abb_dict = clean_and_sort_abbreviations(abb_dict)

    matched_abbs = clean_and_sort_abbreviations(matched_abbs)
    return matched_abbs, abb_dict

def search_abbs_in_text(doc, matched_abbs, abb_dict):
    """
    Extracts text from the document paragraphs until the stop section.
    Checks the text for abbreviations from abb_dict that were not initially detected.
    Returns an updated DataFrame of matched abbreviations.
    """
    stop_section="Список литературы"
    found_text = []
    
    for para in doc.paragraphs:
        if stop_section.lower() in para.text.lower() and para.style.name == 'Heading 1':
            break
        found_text.append(para.text)

    found_text = " ".join(found_text)
    
    # Check full text for any other abb in the dictionary not recognized
    for abb in abb_dict['abbreviation']:
        if re.search(rf'(?<!\w){re.escape(abb)}(?!\w)', found_text) and abb not in doc_abbs:
            matched_abbs = pd.concat([matched_abbs, abb_dict[abb_dict['abbreviation'] == abb]])

    matched_abbs = clean_and_sort_abbreviations(matched_abbs)
    return matched_abbs

def review_one_letter_abbreviations(matched_abbs, doc, abb_dict):
    """
    Review one-letter abbreviations in the matched_abbs DataFrame.
    Ask the user if they want to add each abbreviation to the table.
    Returns an updated matched_abbs DataFrame.
    """
    one_letter_abbs = matched_abbs[matched_abbs['abbreviation'].str.len() == 1].copy()
    
    if not one_letter_abbs.empty:
        print("\n[INFO] One-letter abbreviations detected:")
        
        to_keep = []
        for abb in one_letter_abbs['abbreviation'].unique():
            descriptions = one_letter_abbs[one_letter_abbs['abbreviation'] == abb]
            
            if len(descriptions) > 1:
                print(f"\nAbbreviation: '{abb}' has multiple descriptions:")
                for i, desc in enumerate(descriptions['description'].unique(), start=1):
                    print(f"- {desc}")
                                
                # Ask if user wants to handle or skip
                choice = input(f"Do you want to add '{abb}' to the table? (y/n): ").strip().lower()

                if choice == 'y':
                    matched_abbs, abb_dict = handle_multiple_descriptions(
                        abb, descriptions['description'].unique(), abb_dict, matched_abbs, doc
                    )
                    to_keep.append(abb)
                else:
                    print(f"[INFO] '{abb}' will be excluded.")
            else:
                desc = descriptions['description'].values[0]
                print(f"\nAbbreviation: '{abb}'")
                print(f" - {desc}")
                choice = input(f"Do you want to add this description for '{abb}'? (y/n/custom): ").strip().lower()
                
                if choice == 'y':
                    to_keep.append(abb)
                elif choice == 'custom':
                    custom_desc = input(f"Enter custom description for '{abb}': ").strip()
                    if custom_desc:
                        new_entry = pd.DataFrame([{'abbreviation': abb, 'description': custom_desc}])
                        abb_dict = pd.concat([abb_dict, new_entry], ignore_index=True)
                        matched_abbs = pd.concat([matched_abbs, new_entry], ignore_index=True)
                        print(f"[INFO] Custom description for '{abb}' added.")
                        to_keep.append(abb)
                    else:
                        print(f"[INFO] No custom description provided. '{abb}' will be excluded.")
                else:
                    print(f"[INFO] '{abb}' will be excluded.")

        matched_abbs = matched_abbs[
            (matched_abbs['abbreviation'].str.len() > 1) | 
            (matched_abbs['abbreviation'].isin(to_keep))
        ]                

    return matched_abbs, abb_dict

# ------------------------------
# Formatting helper functions
# ------------------------------

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
        
# ------------------------------
# Output generation
# ------------------------------

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

    # Create table (header row + body, 2 columns)
    table = doc.add_table(rows=1, cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Аббревиатура'
    hdr_cells[1].text = 'Расшифровка'

    # Format header
    for cell in hdr_cells:
        set_cell_border(cell)
        format_paragraph_spacing(cell)
        for run in cell.paragraphs[0].runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    # Table body
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

    # Enforce column widths
    for row in table.rows:
        row.cells[0].width = Cm(3.7)
        row.cells[1].width = second_col_width

    # Save
    out_path = 'output/abbreviations_table.docx'
    os.makedirs('output', exist_ok=True)
    doc.save(out_path)
    print(f"Abbreviation table saved to {out_path}")

# -------------------------------------------------------------------
# Additional Checks
# -------------------------------------------------------------------

def check_inconsistencies(matched_abbs):
    """
    1) Print how many abbreviations have more than one unique description.
    2) Print how many descriptions are used by more than one abbreviation.
    """
    # Abbreviations with multiple unique descriptions
    multi_desc = (matched_abbs.groupby('abbreviation')['description']
                            .nunique()
                            .reset_index()
                            .query('description > 1'))
    count_mult_desc = len(multi_desc)
    if count_mult_desc > 0:
        print(f"\n[INFO] {count_mult_desc} abbreviation(s) have multiple descriptions:")
        duplicates = matched_abbs[matched_abbs['abbreviation'].isin(multi_desc['abbreviation'])]
        print(duplicates)
    else:
        print("\n[INFO] No abbreviations with multiple descriptions.")

    # Descriptions used by multiple abbreviations
    multi_abbs = (matched_abbs.groupby('description')['abbreviation']
                             .nunique()
                             .reset_index()
                             .query('abbreviation > 1'))
    count_mult_abbs = len(multi_abbs)
    if count_mult_abbs > 0:
        print(f"\n[INFO] {count_mult_abbs} description(s) are shared by multiple abbreviations:")
        duplicates = matched_abbs[matched_abbs['description'].isin(multi_abbs['description'])]
        print(duplicates)
    else:
        print("\n[INFO] No descriptions are shared by multiple abbreviations.")

def review_new_entries(abb_dict_before, abb_dict_after):
    """
    Identify newly added rows (by abbreviation+description) in abb_dict,
    and ask user whether to save.
    """
    merged = abb_dict_after.merge(
        abb_dict_before,
        on=['abbreviation', 'description'],
        how='left',
        indicator=True
    )
    new_entries = merged[merged['_merge'] == 'left_only'][['abbreviation', 'description']]

    if not new_entries.empty:
        print("\n[INFO] The following new entries have been identified in the abbreviation dictionary:")
        print(new_entries)
        confirm = input("\nAre you sure you want to permanently update the dictionary with these new entries? (y/n): ").strip().lower()
        if confirm == 'y':
            abb_dict_after.to_csv(ABB_DICT_PATH, index=False, encoding='utf-8-sig')
            print("[INFO] Abbreviation dictionary updated.")
        else:
            print("[INFO] User chose not to save new entries. No changes will be written.")
    else:
        print("\n[INFO] No new entries found. The abbreviation dictionary was not updated.")

# ------------------------------
# Main script
# ------------------------------

if __name__ == "__main__":
    doc_file = [f for f in os.listdir(DOC_PATH) if f.endswith('.docx') and not f.startswith('~$')]
    if len(doc_file) != 1:
        raise FileNotFoundError("Expected exactly one .docx file in the folder.")
    
    doc_path = os.path.join(DOC_PATH, doc_file[0])
    print(f"[INFO] Processing document: {doc_path}")

    doc = Document(doc_path)
    doc_abbs = extract_abbreviations_from_doc(doc)
    
    abb_dict = load_abbreviation_dict()
    matched_abbs, abb_dict_updated = match_and_update_abbreviations(doc, doc_abbs, abb_dict)
    matched_abbs = search_abbs_in_text(doc, matched_abbs, abb_dict)
    matched_abbs, abb_dict_updated = review_one_letter_abbreviations(matched_abbs, doc, abb_dict_updated)
    # Generate abbreviation table
    generate_abbreviation_table(matched_abbs)

    # Compare changes
    initial_abbs = get_all_abbreviations(DOC_PATH)
    compare_abbreviations(old_abbs=initial_abbs, new_abbs=matched_abbs)

    # Check for abbreviations with multiple unique descriptions
    check_inconsistencies(matched_abbs)

    # Identify new entries that were not in the original dictionary for user review
    review_new_entries(abb_dict, abb_dict_updated)
