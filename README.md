# Abbreviation Table Generator
A Python app that extracts, manages, and generates abbreviation tables from Word documents.

## Main Functionalities:
- Mixed Character Detection & Correction
  - Detects and corrects mixed Cyrillic/Latin characters in abbreviations
  - Helps prevent duplicate entries with different character sets
- Custom Description Management
  - Handles new abbreviation descriptions
  - Checks for similar existing descriptions using fuzzy matching
- Multiple Description Handling
  - Manages cases where abbreviations have multiple possible descriptions
  - Allows user to select or create new descriptions
- Single Occurrence Abbreviations
  - Special handling for abbreviations that appear only once
- Context-aware decision making
- Quality Control Features
  - Inconsistency checking
  - Review of one-letter abbreviations
- Automatically update the abbreviation list (abb_dict.csv) with new entries.
- Output a Word document containing a table of abbreviations found in the supplied document.

## How to Run:

- Extract abbreviations from multiple documents with extract_abbs.py.
- Generate an abbreviation table for a specific document by running process_doc.py.
- New abbreviations will be added to abb_dict.csv after the user fills in missing descriptions.