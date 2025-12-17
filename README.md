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
- Functionality to check for similar existing descriptions for new entries (e.g. using fuzzy matching)
- Settings to customize the view (e.g. the context window length and the number of context lines displayed)
- Counters for skipped abbreviations and newly added entries
- Add English versions of the interface and the dictionary

# Installation

## 1. Create a directory and clone the repository

```bash
mkdir <project_directory>
cd <project_directory>
git clone https://github.com/T0chka/Abbreviator.git
```

## 2. Set up a virtual environment

Go to the cloned repository:

```bash
cd Abbreviator
```

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Create a database
In the repository in the abb_app/data folder there is a file abb_dict.csv. This file contains a dictionary of abbreviations and their translations for example, which you can use for testing. You can replace it with your own dictionary, saving the CSV format:

```
abbreviation,description
AI,Artificial Intelligence
```

Apply migrations and import the dictionary into the database:

```bash
python manage.py makemigrations abb_app
python manage.py migrate
python manage.py import_abbreviations abb_app/data/abb_dict.csv
```

## 5. Run the development server
```bash
python manage.py runserver
```

## 6. Open the application in your browser

```
http://127.0.0.1:8000/
```