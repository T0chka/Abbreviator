# Abbreviation Table Generator
A Python app that extracts, manages, and generates abbreviation tables from Word documents.

## Live Demo
The project is currently live and running at [https://datadelic.dev/abbreviator](https://datadelic.dev/abbreviator). Please note that the work is still in progress.


## Main Functionalities:
- Allows to select one of the existing descriptions or create a new one
- Presents the context of the abbreviation in the document
- Detects mixed Cyrillic/Latin characters in abbreviations, which helps prevent duplicate entries with different character sets
- Extract existing abbreviation table from the document and compare it with the new one
- Outputs a Word document containing a table of abbreviations found in the supplied document

## TODO:
- Optimize performance for larger documents.
- Checks for similar existing descriptions using fuzzy matching.
- Automatically updates the abbreviation list with new entries
- Implement additional features based on user feedback.
- Implement automated descriptions formatting
- Implement LLM-based descriptions generation