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
    
    # Convert abbreviation letters to uppercase (e.g. "FDA")
    abbr_letters = ''.join(re.findall(r'[A-Za-z]', abbr)).upper()
    
    # Split the English description into tokens (words + punctuation)
    tokens = re.findall(r"\w+(?:[-/]\w+)*|[^\w\s]", english_desc)
    
    # Pointer to track the next abbreviation letter
    abbr_idx = 0
    
    def maybe_capitalize(token):
        nonlocal abbr_idx
        if abbr_idx < len(abbr_letters):
            first_char = token[0]
            # Match ignoring case
            if first_char.upper() == abbr_letters[abbr_idx]:
                # Capitalize the first letter
                token = first_char.upper() + token[1:]
                abbr_idx += 1
        return token
    
    # Build the new English description by capitalizing in order
    new_tokens = []
    for token in tokens:
        # If it's alphanumeric (word), check for a match
        if re.match(r'^\w+$', token):
            new_tokens.append(maybe_capitalize(token))
        else:
            # punctuation or something else
            new_tokens.append(token)
    
    # Rejoin tokens without adding spaces around specific punctuation
    formatted_english = "".join(
        [t if i == 0 or t in ['-', '/'] or new_tokens[i - 1] in ['«', '/'] or t in ['»'] 
        else f" {t}" if new_tokens[i - 1].isalnum() 
        else t
        for i, t in enumerate(new_tokens)]
    ).strip()
    
    return formatted_english.strip() + (' ' + russian_desc if russian_desc else '')

def clean_and_sort_abbreviations(abb_dict):
    """
    Cleans, deduplicates, and sorts the abbreviation DataFrame.
    - Strips whitespace from 'abbreviation' and 'description'.
    - Capitalizes words in 'description' using format_abbreviation().
    - Removes duplicates.
    - Sorts by ['abbreviation', 'description'].
    - Resets the index.
    """
    abb_dict['abbreviation'] = abb_dict['abbreviation'].str.strip()
    abb_dict['description'] = abb_dict['description'].str.strip()

    # Apply format_abbreviation only if abbreviation contains English letters
    mask = abb_dict['abbreviation'].str.contains(r'[A-Za-z]')
    abb_dict.loc[mask, 'description'] = abb_dict[mask].apply(format_abbreviation, axis=1)

    # Capitalize the first letter after any leading digits (if present)
    abb_dict['description'] = abb_dict['description'].apply(
        lambda x: re.sub(
            r'^(\d*)([a-zA-ZА-Яа-яЁё])',
            lambda m: m.group(1) + m.group(2).upper(),
            x
        ) if x else x
    )

    return (abb_dict
            .drop_duplicates()
            .sort_values(by=['abbreviation', 'description'])
            .reset_index(drop=True)
           )

if __name__ == "__main__":
    ABB_DICT_PATH = "data/abb_dict.csv"
    FORMATTED_DICT_PATH = "data/formatted_abb_dict.csv"

    abb_dict = pd.read_csv(ABB_DICT_PATH)
    old_abb_dict = abb_dict.copy(deep=True)
    old_abb_dict['abbreviation'] = old_abb_dict['abbreviation'].str.strip()
    old_abb_dict['description'] = old_abb_dict['description'].str.strip()

    abb_dict = clean_and_sort_abbreviations(abb_dict)

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