# Abbreviation Table Generator
A Django web application that extracts and manages abbreviations from Word documents, and generates an abbreviation table with their descriptions.

## Live Demo
The project is currently live and running at [https://datadelic.dev/abbreviator](https://datadelic.dev/abbreviator).
*Note: The application is a work in progress.*


## Main features:
- Process Word documents only
- Automatically extract abbreviations and their context
- Use a specially compiled dictionary of abbreviations and their descriptions commonly used in medical documents
- Generate descriptions using specialized language models
- Select an existing description from    the dictionary or add a new one
- Detect mixed Cyrillic/Latin characters in abbreviations
- Compare existing abbreviation table (if present) with the newly generated table
- Load a table with user-selected abbreviation-description pairs in Word format.

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

Go to the cloned repository and create and activate a virtual environment:

```bash
cd Abbreviator
python3 -m venv venv
# Windows
venv\Scripts\activate 
# Linux/Mac
source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Database Setup

The application can work with or without a pre-populated abbreviation dictionary.
First, create the database structure:
```bash
python manage.py makemigrations abb_app
python manage.py migrate
```
### Populating the dictionary (Optional)

You have three options for adding abbreviations to the database:

1. **Start with an empty dictionary** and add entries gradually through the interface.

2. **Extract from Word documents**:
   ```bash
   python manage.py extract_abbs_word_to_csv \
   --input-dir docs/ \
   --output-file extracted.csv
   python manage.py import_abbs_csv_to_db extracted.csv
   ```

3. **Create your own custom CSV file** with the format:
   ```
   abbreviation,description
   AI,Artificial Intelligence
   MRI,Magnetic Resonance Imaging
   ```
   Then import it:
   ```bash
   python manage.py import_abbs_csv_to_db your_dictionary.csv
   ```

### Dictionary Management

Newly added abbreviations start with the `for_review` status. To approve them:

1. Access the Django admin interface at `/admin/`
2. Log in with your admin credentials
3. Navigate to the AbbreviationEntry model
4. Select entries and change their status to "Approved"

Only approved abbreviations will appear in the public dictionary view and be used for suggestions.

## 5. Run the development server
```bash
python manage.py runserver
```
And open the application in your browser: http://127.0.0.1:8000/

# Language Model Integration

The application integrates with language models via Ollama API:

1. Install Ollama and follow instructions at [official website](https://ollama.ai/)

2. Configure server address in settings.py:
   ```python
   OLLAMA_HOST = 'http://localhost:11434'  # Or remote server address
   OLLAMA_MODEL = 'medical'  # Model name
   OLLAMA_TEMPERATURE = 0.6
   OLLAMA_TOP_P = 0.6
   ```

3. Or use environment variables:
   ```bash
   export OLLAMA_HOST=http://your_server:11434
   ```
For detailed instructions on extracting, cleaning, training, and testing models, please refer to:
[Model Integration Documentation](abb_app/model_integration/README.md). This documentation covers the complete workflow for training and using Large Language Models to process abbreviations.

# Project Structure

- `abb_app/` - Main Django application
  - `data/` - Directory for data and dictionaries
  - `benchmarks/` - Benchmarking results
  - `management/commands/` - Django management commands
  - `model_integration/` - Language model integration
  - `static/` - Static files (CSS, JavaScript)
  - `templates/` - HTML templates
  - `utils.py` - Utilities for processing abbreviations
  - `views.py` - Django views

## Development Recommendations

1. **Data Files**:
   - CSV files with data should not be added to the repository
   - Use the `abb_app/data/` directory for local data storage

2. **Model Setup**:
   - API access requires an Ollama server
   - For local development, install Ollama or specify a remote server

3. **Testing**:
   - Use the `test_model.py` command to check generation quality
   - Use test drive mode through the web interface for demonstrations