# Abbreviator

**Abbreviation extraction and validation for DOCX documents.**

[Live demo](https://datadelic.dev/abbreviator/) — includes a guided demo with a sample document.

Abbreviator is a Django web application for reviewing abbreviations in documents. It extracts abbreviations with their context, checks them against a curated dictionary, highlights mixed Cyrillic/Latin spelling, helps resolve missing descriptions, and exports a clean abbreviation table back to Word.

The current dictionary is focused on medical and pharmaceutical documentation, while the extraction and review workflow itself is domain-agnostic.

## Key features

- Extracts abbreviations and context from `.docx` documents.
- Suggests approved descriptions from the project dictionary and allows manual review.
- Detects mixed Cyrillic/Latin characters and proposes the canonical spelling when known.
- Uses AI to suggest a description.
- Compares detected abbreviations with an abbreviation table already present in the document.
- Provides global context-display settings with per-card overrides.
- Supports configurable table generation.
- Exports the reviewed abbreviation table as `.docx`.

## Privacy by design

Uploaded documents and extracted session data expire after 10 minutes of inactivity. Production cleanup removes expired documents and Django session records every 5 minutes.

AI generation is opt-in for each request. Only the abbreviation and the context fragments shown to the user are sent to the GigaChat API after explicit confirmation; the full document and filename are not sent. Document text is not written to production application logs or analytics.

## Architecture

- **Backend:** Python 3.11, Django 5.2
- **Document processing:** `python-docx`
- **Dictionary:** SQLite with approved / review / rejected entries
- **AI:** GigaChat API with structured output
- **Frontend:** Django templates, vanilla JavaScript and CSS
- **Production:** Gunicorn, nginx, systemd
- **Dependency management:** `uv`

Application logic is separated into focused services for abbreviation handling, extraction, document generation, uploads, session cleanup, and AI integration. Production configuration is documented in [`deploy/`](deploy/README.md).

## Local development

```bash
git clone https://github.com/T0chka/Abbreviator.git
cd Abbreviator
uv sync
```

Create a local `.env`:

```env
SECRET_KEY=local-development-key
```

Then initialize the database and run the application:

```bash
uv run python manage.py migrate
uv run python manage.py runserver
```

AI generation additionally requires the GigaChat environment settings used by `abb_project/settings.py`.

## Tests

```bash
uv run python manage.py test
```

The regression suite covers extraction, document/session lifecycle, uploads, dictionary updates, comparison logic, views, and AI integration.

## Production deployment

The repository includes the current Gunicorn, nginx, systemd, cleanup-timer, and deployment configuration in [`deploy/`](deploy/README.md).

## License

See [`LICENSE`](LICENSE).
