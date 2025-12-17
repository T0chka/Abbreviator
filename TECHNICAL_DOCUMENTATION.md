# Technical Documentation for Abbreviator

## Architecture Overview

The project is a Django application for automatic processing of medical documents to extract and decode abbreviations. The system uses a local language model (LLM) to generate decodings for unknown abbreviations.

## Technology Stack

- **Backend**: Django 5.1.4
- **Database**: SQLite3 (default)
- **Language Model**: Ollama (local installation)
- **Document Processing**: python-docx
- **Validation**: Pydantic
- **HTTP Client**: requests, httpx
- **Fuzzy matching**: thefuzz, RapidFuzz

## Project Structure

```
Abbreviator/
├── abb_project/           # Main Django settings
│   ├── settings.py       # Application configuration
│   ├── urls.py          # Main URL routes
│   ├── wsgi.py          # WSGI configuration
│   └── asgi.py          # ASGI configuration
├── abb_app/              # Main application
│   ├── models.py        # Data models
│   ├── views.py         # Views (controllers)
│   ├── urls.py          # Application URL routes
│   ├── admin.py         # Administrative interface
│   ├── utils.py         # Utilities and business logic
│   └── model_integration/ # Language model integration
│       ├── client.py    # Client for working with Ollama
│       └── test_model_connection.py
├── media/               # Uploaded files
├── db.sqlite3          # SQLite database
├── requirements.txt    # Python dependencies
└── manage.py           # Django management
```

## Data Models

### AbbreviationEntry

Main model for storing the abbreviation dictionary:

```python
class AbbreviationEntry(models.Model):
    abbreviation = models.CharField(max_length=50, db_index=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    highlighted = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('approved', 'Approved'),
            ('for_review', 'For Review'),
            ('rejected', 'Rejected')
        ],
        default='for_review',
        db_index=True
    )
```

**Model Fields:**
- `abbreviation`: The abbreviation itself (indexed field)
- `description`: Abbreviation decoding
- `created_at/updated_at`: Timestamps
- `highlighted`: Additional information for display
- `status`: Approval status (approved/for_review/rejected)

**Indexes:**
- `abbreviation` - for fast search
- `status` - for filtering by status
- Unique constraint on the pair `(abbreviation, description)`

## Language Model Integration

### ModelClient

Class for interacting with the local Ollama model:

```python
class ModelClient:
    def __init__(self, host="http://localhost:11434", model="llama3.2"):
        self.host = host
        self.model = model
```

**Configuration:**
- **Host**: `http://localhost:11434` (standard Ollama port)
- **Model**: `llama3.2` (default)
- **Response Format**: JSON
- **Generation Parameters**:
  - `temperature`: 0.1 (low creativity)
  - `top_p`: 0.1 (focus on most probable tokens)

**Security Protocol:**
- Local connection (localhost)
- HTTP (not HTTPS) - for local development
- JSON response validation
- Connection error handling

### Decoding Generation Process

1. **Dictionary Check**: First, check if the abbreviation exists in the database
2. **Prompt Generation**: Create a specialized prompt for medical terminology
3. **Model Request**: Send HTTP POST request to Ollama API
4. **Response Validation**: Parse JSON and validate through Pydantic
5. **Saving**: New decodings are saved with status 'for_review'

## File Processing

### Upload and Storage

**Media Files Path:**
```python
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'
```

**Upload Process:**
1. Generate unique session_id based on filename and timestamp
2. Save file to `media/` folder with name `{session_id}.{extension}`
3. Clean up old files (older than 0 hours by default)

**Limitations:**
- Maximum file size: 1MB (`DATA_UPLOAD_MAX_MEMORY_SIZE = 1048576`)
- Maximum number of files: 10 (`DATA_UPLOAD_MAX_NUMBER_FILES = 10`)
- Supported formats: .docx

### Document Processing

**Text Extraction:**
- Skip sections: "СПИСОК ЛИТЕРАТУРЫ", "Список использованной литературы"
- Extract only relevant content
- Process abbreviation tables

**Abbreviation Search:**
- Regular expressions for finding uppercase letters
- Exclude Roman numerals and long words (>8 characters)
- Count frequency of occurrence
- Extract context (50 characters before and after)

## Security Settings

### Environment Variables

```python
SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-default-secret-key'
DEBUG = os.environ.get('DEBUG') == 'True' if 'DEBUG' in os.environ else True
```

**Required Variables for Production:**
- `SECRET_KEY`: Django secret key
- `DEBUG`: Debug mode (False for production)
- `STATIC_URL`: URL for static files
- `STATIC_ROOT`: Path to static files

### Security Settings

```python
ALLOWED_HOSTS = ['datadelic.dev', '127.0.0.1']
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

**For Production:**
- Proxy header configuration
- Enforce HTTPS usage
- Restrict allowed hosts

## Installation and Deployment

### Local Installation

1. **Clone Repository:**
```bash
git clone <repository-url>
cd Abbreviator
```

2. **Create Virtual Environment:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

3. **Install Dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure Environment Variables:**
```bash
export SECRET_KEY="your-secret-key-here"
export DEBUG="False"  # for production
```

5. **Database Migrations:**
```bash
python manage.py makemigrations
python manage.py migrate
```

6. **Create Superuser:**
```bash
python manage.py createsuperuser
```

7. **Run Server:**
```bash
python manage.py runserver
```

### Ollama Installation

1. **Download and Install Ollama:**
```bash
# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows/Mac - download from https://ollama.ai
```

2. **Start Ollama Server:**
```bash
ollama serve
```

3. **Load Model:**
```bash
ollama pull llama3.2
```

4. **Test Connection:**
```bash
python abb_app/model_integration/test_model_connection.py
```

### Production Configuration

1. **Web Server Configuration (Nginx):**
```nginx
location /abbreviator/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

2. **WSGI Configuration (Gunicorn):**
```bash
pip install gunicorn
gunicorn --bind 0.0.0.0:8000 abb_project.wsgi:application
```

3. **Collect Static Files:**
```bash
python manage.py collectstatic
```

## Monitoring and Logging

### Logging

```python
logger = logging.getLogger('abb_app')
logger.setLevel(logging.DEBUG)
```

**Logging Levels:**
- DEBUG: Detailed process information
- INFO: General operation information
- ERROR: Errors and exceptions

### Performance Monitoring

**Key Metrics:**
- Document processing time
- Number of model requests
- Uploaded file sizes
- Number of found abbreviations

## Backup

### Database

```bash
# Create SQLite backup
cp db.sqlite3 backup/db_$(date +%Y%m%d_%H%M%S).sqlite3
```

### Media Files

```bash
# Backup uploaded files
tar -czf backup/media_$(date +%Y%m%d_%H%M%S).tar.gz media/
```

## Scaling

### Horizontal Scaling

1. **Load Balancer**: Nginx with multiple Django instances
2. **Database**: Migration to PostgreSQL for production
3. **Caching**: Redis for sessions and cache
4. **File Storage**: S3-compatible storage

### Performance Optimization

1. **Database Indexes**: Already configured for main queries
2. **Caching**: Caching model results
3. **Asynchronous Processing**: Celery for background tasks
4. **CDN**: For static files

## Troubleshooting

### Common Issues

1. **Model Connection Error:**
   - Check Ollama is running: `ollama serve`
   - Check availability: `curl http://localhost:11434/api/tags`

2. **File Upload Errors:**
   - Check permissions for `media/` folder
   - Check file size (limit 1MB)

3. **Database Errors:**
   - Run migrations: `python manage.py migrate`
   - Check permissions for `db.sqlite3`

### Diagnostic Logs

```bash
# Django logs
tail -f logs/django.log

# Ollama logs
ollama logs

# Web server logs
tail -f /var/log/nginx/error.log
```

## API Endpoints

### Main Routes

- `GET /` - File upload
- `POST /` - Process uploaded file
- `GET /process/<session_id>/` - Process file by session
- `POST /update_abbreviation/` - Update abbreviation
- `POST /update_difference_section/` - Update difference section
- `POST /make_abbreviation_table/` - Generate table
- `GET /dictionary/` - View dictionary
- `GET /admin/` - Administrative interface

### Response Formats

**JSON Responses:**
```json
{
    "success": true,
    "session_id": "abc123def456",
    "error": "Error description"
}
```

**File Responses:**
- Content-Type: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- Content-Disposition: `attachment; filename=abbreviation_table.docx`

## Conclusion

This documentation contains all necessary technical information for deployment and support of the Abbreviator system. The system is designed to work in a local environment with the ability to scale for production.
