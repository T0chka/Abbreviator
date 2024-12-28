import os
import pandas as pd
from docx import Document
from lxml import etree
from collections import defaultdict


folder_path = 'data/abb_examples/'
abb_dict_path = "data/abb_dict.csv"

SECTION_PATTERN = 'СПИСОК СОКРАЩЕНИЙ'
NAMESPACE = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

def extract_abb_table(doc, section_pattern=SECTION_PATTERN):
    """
    Iterate over the document blocks. Once the specified `section_pattern` is found,
    return the first table that appears right after that section.
    """
    found_section = False

    for block in doc.element.body:
        if block.tag.endswith('p'):
            para_text = ''.join(
                node.text for node in block.findall('.//w:t', namespaces=NAMESPACE) if node.text
            )
            if section_pattern.casefold() in para_text.casefold():
                para_style = block.find('.//w:pStyle', namespaces=NAMESPACE)
                outline_level = block.find('.//w:outlineLvl', namespaces=NAMESPACE)
                if para_style is not None and para_style.attrib.get(f"{{{NAMESPACE['w']}}}val") == "Heading1":
                    found_section = True
                    continue
                        
                elif outline_level is not None and outline_level.attrib.get(f"{{{NAMESPACE['w']}}}val") == "0":
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

def get_all_abbreviations(folder_path, section_pattern=SECTION_PATTERN):
    """
    Loop through all .docx files in `folder_path`, extract the relevant table, parse it,
    and append to a single DataFrame with columns ['abbreviation', 'description'].
    """
    all_abbreviations = pd.DataFrame(columns=["abbreviation", "description"])

    for file_name in os.listdir(folder_path):
        if file_name.endswith('.docx') and not file_name.startswith('~$'):
            file_path = os.path.join(folder_path, file_name)
            
            doc = Document(file_path)
            table_element = extract_abb_table(doc, section_pattern)

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

    combined_abbs = pd.concat([existing_abbs, new_abbs], ignore_index=True)\
                  .drop_duplicates()\
                  .sort_values(by=["abbreviation", "description"])

    new_entries_count = len(combined_abbs) - len(existing_abbs)

    print(f"{new_entries_count} new abbreviations added.")

    inconsistent = (combined_abbs.groupby("abbreviation")["description"]
    .nunique()
    .reset_index()
    .query("description > 1")
    )
    inconsistent = combined_abbs[combined_abbs["abbreviation"].isin(inconsistent["abbreviation"])]
    print("Abbreviations with different descriptions:")
    print(inconsistent)

    combined_abbs.to_csv("data/abb_dict.csv", index=False)
    print("Abbreviations extracted and saved to data/abb_dict.csv")