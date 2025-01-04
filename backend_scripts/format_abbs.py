import pandas as pd
import re

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

if __name__ == "__main__":
    ABB_DICT_PATH = "data/abb_dict.csv"
    FORMATTED_DICT_PATH = "data/abb_dict.csv" #"data/formatted_abb_dict.csv"

    abb_dict = pd.read_csv(ABB_DICT_PATH)
    old_abb_dict = abb_dict.copy(deep=True)
    old_abb_dict['abbreviation'] = old_abb_dict['abbreviation'].str.strip()
    old_abb_dict['description'] = old_abb_dict['description'].str.strip()

    clean_and_sort_abbreviations(abb_dict)

    merged = abb_dict.merge(
        old_abb_dict,
        on=['abbreviation', 'description'],
        how='outer',
        indicator=True,
        suffixes=('_new', '_old')
    )

    new_or_changed = merged[merged['_merge'] == 'left_only']
    changed_existing = merged[
        (merged['_merge'] == 'left_only') & 
        (merged['abbreviation'].isin(old_abb_dict['abbreviation'].values))
    ]

    if not new_or_changed.empty:
        print("[INFO] The following abbreviations had their descriptions changed or added:\n")
        for idx, row in new_or_changed.iterrows():
            print(f"Abbreviation: {row['abbreviation']}")
            old_desc = merged[
                (merged['abbreviation'] == row['abbreviation']) & 
                (merged['_merge'] == 'right_only')
            ]['description'].values
            if len(old_desc) > 0:
                print(f"OLD: [{old_desc[0]}]")
                print(f"NEW: [{row['description']}]")
            else:
                print(f"NEW: [{row['description']}]")
                print(f"Status: New")
            print()
    else:
        print("[INFO] No descriptions have changed.\n")

    abb_dict.to_csv(FORMATTED_DICT_PATH, index=False, encoding='utf-8-sig')
    print(f"[INFO] Successfully saved changes to {FORMATTED_DICT_PATH}")