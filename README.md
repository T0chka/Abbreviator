# Abbreviator

**DOCX abbreviation extraction, review, validation, and table generation.**

[![CI](https://github.com/T0chka/Abbreviator/actions/workflows/ci.yml/badge.svg)](https://github.com/T0chka/Abbreviator/actions/workflows/ci.yml)

[Live demo](https://datadelic.dev/abbreviator/) | [Source code](https://github.com/T0chka/Abbreviator)

Abbreviator is a Django web application for turning abbreviations found in Word documents into a reviewed abbreviation table. It extracts abbreviations with their surrounding context, checks them against a curated dictionary, helps resolve missing descriptions, compares the reviewed result with an existing abbreviation table, and exports the final table back to `.docx`.

The bundled dictionary and optional AI prompt are aimed at medical and scientific documents. The document-processing and review workflow itself is not tied to a specific therapeutic area or study type.

## Workflow

```text
DOCX document
    ↓
Abbreviation extraction + context collection
    ↓
Dictionary lookup + Cyrillic/Latin homoglyph checks
    ↓
Human review + optional AI suggestion
    ↓
Comparison with the document's existing abbreviation table
    ↓
Preview and configurable table generation
    ↓
Reviewed DOCX export
```

The live site includes a guided demo using a bundled sample document, so the full workflow can be explored without uploading a file.

## Key features

- Extracts abbreviations from `.docx` documents and keeps context in document order.
- Suggests one or more approved descriptions from a curated dictionary.
- Allows each abbreviation to be confirmed, removed, or entered manually.
- Detects visually ambiguous Cyrillic/Latin homoglyphs and can normalize spelling to the approved dictionary form.
- Compares the reviewed abbreviations with a table already present in the source document.
- Provides global context-display settings with per-abbreviation overrides.
- Generates a configurable abbreviation table with an in-browser preview.
- Exports the reviewed table back to Word.
- Preserves review state across page refreshes for the active document.
- Provides a read-only public dictionary and a separate Django admin moderation workflow.

## Optional AI suggestions

AI generation is deliberately secondary to the dictionary and manual review workflow. It is requested for an individual abbreviation only after explicit user confirmation.

For an AI request, Abbreviator sends only:

- the abbreviation;
- the context fragments currently shown for that abbreviation.

The full document and filename are not sent to the AI service. The current integration uses the GigaChat API with structured JSON output.

## Privacy and document lifecycle

Uploaded documents and extracted review state expire after **10 minutes of inactivity**. In production, a systemd timer runs cleanup every 5 minutes and removes both expired documents and expired Django sessions.

Document text is not written to application logs or analytics.

## Technical highlights

- **Backend:** Python 3.11, Django 5.2
- **DOCX processing:** `python-docx`
- **Dictionary:** SQLite, with approved / review / rejected moderation states
- **AI integration:** GigaChat API via `requests`
- **Frontend:** server-rendered Django templates, vanilla JavaScript, CSS
- **Production:** Gunicorn, nginx, systemd
- **Dependency management:** `uv`
- **CI:** Django checks, migration consistency, JavaScript syntax checks, and regression tests on GitHub Actions

The application logic is split into focused services for extraction, abbreviation handling, document generation, uploads, session lifecycle, and AI integration. UI state that belongs to the active document is kept in the Django session rather than in browser-only persistence.

## Local development

Clone the repository and install the locked dependencies:

```bash
git clone https://github.com/T0chka/Abbreviator.git
cd Abbreviator
uv sync
```

Create `.env` in the project root:

```env
SECRET_KEY=local-development-key
DJANGO_DEBUG=True
```

Initialize the database and start Django:

```bash
uv run python manage.py migrate
uv run python manage.py runserver
```

The core extraction, review, comparison, preview, and export workflow works without AI credentials.

To enable AI suggestions, additionally configure the GigaChat settings consumed by `abb_project/settings.py`, in particular `GIGACHAT_CREDENTIALS`.

## Tests

Run the regression suite with:

```bash
uv run python manage.py test
```

The suite covers extraction, dictionary behavior, review-state persistence, comparison logic, table preparation and rendering, uploads, document/session lifecycle, views, and AI integration.

The CI workflow also runs:

```bash
uv run --frozen python manage.py check
uv run --frozen python manage.py makemigrations --check --dry-run
```

and validates JavaScript syntax before running the Django tests.

## Production deployment

The repository contains the production Gunicorn, nginx, systemd, cleanup-timer, and deployment configuration under [`deploy/`](deploy/README.md).

The live deployment is served at:

**https://datadelic.dev/abbreviator/**

## License

MIT License. See [`LICENSE`](LICENSE).
