import os
import re
import pandas as pd
from docx import Document

# Local imports
from .format_abbs import clean_and_sort_abbreviations

folder_path = "data/abb_examples/"
ABB_DICT_PATH = "data/abb_dict.csv"
SECTION_PATTERNS = ['ПЕРЕЧЕНЬ СОКРАЩЕНИЙ И ОПРЕДЕЛЕНИЯ ТЕРМИНОВ', 'СПИСОК СОКРАЩЕНИЙ']
NAMESPACE = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

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

def get_all_abbreviations(folder_path, section_patterns=SECTION_PATTERNS):
    """
    Loop through all .docx files in `folder_path`, extract the relevant table, parse it,
    and append to a single DataFrame with columns ['abbreviation', 'description'].
    """
    all_abbs = pd.DataFrame(columns=['abbreviation', 'description'])

    for file_name in os.listdir(folder_path):
        if file_name.endswith('.docx') and not file_name.startswith('~$'):
            file_path = os.path.join(folder_path, file_name)
            
            doc = Document(file_path)
            table_element = extract_abb_table(doc, section_patterns)

            if table_element is not None:
                df = parse_table(table_element)
                if df is not None:
                    all_abbs = pd.concat([all_abbs, df], ignore_index=True)
                else:
                    print(f"Table structure error in {file_name}")
            else:
                print(f"No relevant table found in {file_name}")
  
    clean_and_sort_abbreviations(all_abbs)
    return all_abbs

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

def resolve_conflicts(existing_abbs, new_abbs):
    """
    Checks each abbreviation in new_abbs:
      - If it exists in existing_abbs but with a different description,
        prompt the user to choose 'old' or 'new'.
        - If 'old', discard the row from new_abbs.
        - If 'new', update existing_abbs' description to the new one.
        
    Returns updated (existing_abbs, new_abbs).
    """
    rows_to_drop = []

    for idx_new, new_row in new_abbs.iterrows():
        abbreviation_new = new_row['abbreviation']
        description_new = new_row['description']

        match_mask = (existing_abbs['abbreviation'] == abbreviation_new)
        if match_mask.any():
            existing_descriptions = existing_abbs.loc[match_mask, 'description'].unique()

            if description_new in existing_descriptions:
                rows_to_drop.append(idx_new)
            else:
                for old_desc in existing_descriptions:
                    print(f"\n[CONFLICT] Found abbreviation '{abbreviation_new}' with different descriptions:")
                    print(f"  Old: {old_desc}")
                    print(f"  New: {description_new}")
                    choice = input("Which one do you prefer? [1 = old, 2 = new] (default=1): ")

                    if choice.strip() == '2':
                        existing_abbs = existing_abbs[
                            ~((existing_abbs['abbreviation'] == abbreviation_new) &
                              (existing_abbs['description'] == old_desc))
                        ]
                        new_entry = pd.DataFrame(
                            [[abbreviation_new, description_new]],
                            columns=['abbreviation','description']
                        )
                        existing_abbs = pd.concat([existing_abbs, new_entry], ignore_index=True)
                    else:
                        pass

                rows_to_drop.append(idx_new)

    new_abbs = new_abbs.drop(rows_to_drop)
    new_abbs = new_abbs.reset_index(drop=True)
    existing_abbs = existing_abbs.drop_duplicates().reset_index(drop=True)

    return existing_abbs, new_abbs

if __name__ == "__main__":
    if os.path.exists(ABB_DICT_PATH):
        existing_abbs = pd.read_csv(ABB_DICT_PATH)
        print(f"Loaded existing abbreviation dictionary with {len(existing_abbs)} entries.")
    else:
        existing_abbs = pd.DataFrame(columns=['abbreviation', 'description'])

    new_abbs = get_all_abbreviations(folder_path)

    existing_abbs, new_abbs = resolve_conflicts(existing_abbs, new_abbs)

    compare_abbreviations(new_abbs, existing_abbs)

    combined_abbs = pd.concat([existing_abbs, new_abbs], ignore_index=True)
    combined_abbs['description'] = combined_abbs['description'].str.capitalize().str.strip()

    clean_and_sort_abbreviations(combined_abbs)

    new_entries_count = len(combined_abbs) - len(existing_abbs)
    print(f"\n[INFO] {new_entries_count} new abbreviations added.")

    inconsistent = (combined_abbs.groupby('abbreviation')['description']
                    .nunique()
                    .reset_index()
                    .query('description > 1')
                    )

    count_inconsistent = inconsistent['abbreviation'].nunique()
    inconsistent_abbs = combined_abbs[combined_abbs['abbreviation'].isin(inconsistent['abbreviation'])]

    print(f"\n[INFO] Abbreviations with more than one unique description: {count_inconsistent}")
    print(inconsistent_abbs)

    # os.makedirs('data', exist_ok=True)
    # combined_abbs.to_csv("data/abb_dict_review.csv", index=False, encoding='utf-8-sig')
    # print("Abbreviations extracted and saved to data/abb_dict.csv")