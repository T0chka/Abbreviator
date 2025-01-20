# Abbreviation Table Generator
A Python application that extracts, manages, and generates an abbreviation table for Word documents.

## Live Demo
The project is currently live and running at [https://datadelic.dev/abbreviator](https://datadelic.dev/abbreviator).
*Note: The application is a work in progress.*


## Main features:
- Allows you to process Word documents up to 20 MB.
- Uses a specially compiled dictionary of abbreviations commonly used in medical documents.
- Displays the context of abbreviations found in the document.
- Lets you select an existing description or add a new one.
- Detects mixed Cyrillic/Latin characters in abbreviations, helping to avoid duplicate entries with different character sets.
- Extracts an existing abbreviation table from the document and compares it with the newly generated table.
- Generates a Word document containing the abbreviation table with user-selected descriptions.

## TODO:
- Handling of different spellings of the same abbreviation (e.g. "HbA1c" and "HBA1C").
- Functionality to check for similar existing descriptions for new entries (e.g. using fuzzy matching)
- Interactive formatting of descriptions in the input line
- Implement LLM-based description generation
- Settings to customize the view (e.g. the context window length and the number of context lines displayed)
- Counters for skipped abbreviations and newly added entries
- Tutorial within the app
- Add abbreviations from other fields (not just medical) to the dictionary (implement categories/tags)
- Add English versions of the interface and the dictionary
