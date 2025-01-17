# Abbreviation Table Generator
A Python application that extracts, manages, and generates an abbreviation table for Word documents.

## Live Demo
The project is currently live and running at [https://datadelic.dev/abbreviator](https://datadelic.dev/abbreviator).
*Note: The application is a work in progress.*


## Main features:
- Contextual Insights: Displays the context of abbreviations found in the document.
- Description Management: Lets you select an existing description or add a new one.
- Mixed Character Detection: Detects mixed Cyrillic/Latin characters in abbreviations, helping to avoid duplicate entries with different character sets.
- Performance Check: Extracts an existing abbreviation table from the document and compares it with the newly generated table.
- Word Output: Generates a Word document containing the abbreviation table with user-selected descriptions.

## TODO:
- Improve handling of large documents
- Add functionality to check for similar existing descriptions (e.g. using fuzzy matching)
- Automatically update the abbreviation dictionary with new entries (admin-moderated)
- Interactive formatting of descriptions in the input line
- Implement LLM-based description generation
- Add settings to customize the view (e.g. the context window length and the number of context lines displayed)
- Add counters for skipped abbreviations and newly added entries
- Add tutorial within the app
- Implement additional features based on user feedback