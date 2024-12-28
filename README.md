# Abbreviation Table Generator
A Python app that extracts, manages, and generates abbreviation tables from Word documents.

## Features:

Extract abbreviations from .docx files and store them in a CSV (abb_dict.csv).
Identify abbreviations used in the supplied document.
Identify new abbreviations without descriptions (not present in abb_dict.csv) and prompt the user to provide definitions.
Automatically update the abbreviation list (abb_dict.csv) with new entries.
Output a Word document containing a table of abbreviations found in the supplied document.

## How to Run:

Extract abbreviations from multiple documents with extract_abbs.py.
Generate an abbreviation table for a specific document by running process_doc.py.
New abbreviations will be added to abb_dict.csv after the user fills in missing descriptions.