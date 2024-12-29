import os
import pandas as pd
from docx import Document
from lxml import etree
from collections import defaultdict


folder_path = 'data/abb_examples/'
abb_dict_path = "data/abb_dict.csv"

SECTION_PATTERNS = ["ПЕРЕЧЕНЬ СОКРАЩЕНИЙ И ОПРЕДЕЛЕНИЯ ТЕРМИНОВ", "СПИСОК СОКРАЩЕНИЙ"]
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
    Assumes the table has at least two columns: [abbreviation, description].
    """
    rows_data = []
    for row in table_element.findall('.//w:tr', namespaces=NAMESPACE):
        cell_texts = []
        for cell in row.findall('.//w:tc', namespaces=NAMESPACE):
            texts = cell.findall('.//w:t', namespaces=NAMESPACE)
            cell_text = ''.join(t.text for t in texts if t.text)
            cell_texts.append(cell_text.strip())
        rows_data.append(cell_texts)

    df = pd.DataFrame(rows_data)
    if df.shape[1] == 2:
        df.columns = ["abbreviation", "description"]
    return df

def get_all_abbreviations(folder_path, section_patterns=SECTION_PATTERNS):
    """
    Loop through all .docx files in `folder_path`, extract the relevant table, parse it,
    and append to a single DataFrame with columns ['abbreviation', 'description'].
    """
    all_abbreviations = pd.DataFrame(columns=["abbreviation", "description"])

    for file_name in os.listdir(folder_path):
        if file_name.endswith('.docx') and not file_name.startswith('~$'):
            file_path = os.path.join(folder_path, file_name)
            
            doc = Document(file_path)
            table_element = extract_abb_table(doc, section_patterns)

            if table_element is not None:
                df = parse_table(table_element)
                if df is not None:
                    all_abbreviations = pd.concat([all_abbreviations, df], ignore_index=True)
                else:
                    print(f"Table structure error in {file_name}")
            else:
                print(f"No relevant table found in {file_name}")
  
    all_abbreviations = all_abbreviations.drop_duplicates().sort_values(by=["abbreviation", "description"])
    return all_abbreviations

if __name__ == "__main__":
    if os.path.exists(abb_dict_path):
        existing_abbs = pd.read_csv(abb_dict_path)
        print(f"Loaded existing abbreviation dictionary with {len(existing_abbs)} entries.")
    else:
        existing_abbs = pd.DataFrame(columns=["abbreviation", "description"])

    new_abbs = get_all_abbreviations(folder_path)

    combined_abbs = pd.concat([existing_abbs, new_abbs], ignore_index=True)
    combined_abbs['description'] = combined_abbs['description'].str.capitalize()

    combined_abbs = combined_abbs.drop_duplicates()\
        .sort_values(by=["abbreviation", "description"])

    new_entries_count = len(combined_abbs) - len(existing_abbs)

    print(f"{new_entries_count} new abbreviations added.")

    inconsistent = (combined_abbs.groupby("abbreviation")["description"]
    .nunique()
    .reset_index()
    .query("description > 1")
    )
    count_inconsistent = inconsistent["abbreviation"].nunique()
    inconsistent = combined_abbs[combined_abbs["abbreviation"].isin(inconsistent["abbreviation"])]
    print(f"Abbreviations with more than one unique description: {count_inconsistent}")
    print(inconsistent)

    os.makedirs('data', exist_ok=True)
    combined_abbs.to_csv("data/abb_dict.csv", index=False, encoding='utf-8-sig')
    print("Abbreviations extracted and saved to data/abb_dict.csv")