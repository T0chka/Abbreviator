import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase
from django.urls import reverse
from docx import Document

from abb_app.models import AbbreviationEntry
from abb_app.services.sessions import SESSION_FILE_KEY


class ProcessingViewTests(TestCase):
    def test_document_is_processed_and_stored_in_session(self):
        AbbreviationEntry.objects.create(
            abbreviation='T4',
            description='thyroxine',
            status='approved',
        )

        with TemporaryDirectory() as media_root:
            session_id = 'test-session'
            path = Path(media_root) / f'{session_id}.docx'

            doc = Document()
            doc.add_paragraph('У пациента определяли уровень T4.')
            doc.save(path)

            session = self.client.session
            session[SESSION_FILE_KEY] = path.name
            session.save()

            with self.settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_SESSION_TIMEOUT_SECONDS=600,
            ):
                response = self.client.get(f'/process/{session_id}/')
                expiry_age = self.client.session.get_expiry_age()

            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'content.html')
            self.assertGreaterEqual(expiry_age, 590)
            self.assertLessEqual(expiry_age, 600)

            doc_abbs = self.client.session['doc_abbs']
            self.assertEqual(len(doc_abbs), 1)
            self.assertEqual(doc_abbs[0]['abbreviation'], 'T4')
            self.assertEqual(doc_abbs[0]['descriptions'], ['thyroxine'])

    def test_refresh_preserves_reviewed_abbreviation_state(self):
        AbbreviationEntry.objects.create(
            abbreviation='T4',
            description='thyroxine',
            status='approved',
        )

        with TemporaryDirectory() as media_root:
            session_id = 'test-session'
            path = Path(media_root) / f'{session_id}.docx'

            doc = Document()
            doc.add_paragraph('У пациента определяли уровень T4.')
            doc.save(path)

            session = self.client.session
            session[SESSION_FILE_KEY] = path.name
            session.save()

            with self.settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_SESSION_TIMEOUT_SECONDS=600,
            ):
                first = self.client.get(f'/process/{session_id}/')
                update = self.client.post(
                    '/update_abbreviation/',
                    data=json.dumps({
                        'abbreviation': 'T4',
                        'description': 'thyroxine',
                        'action': 'add',
                    }),
                    content_type='application/json',
                )
                refreshed = self.client.get(f'/process/{session_id}/')

            self.assertEqual(first.status_code, 200)
            self.assertEqual(update.status_code, 200)
            self.assertEqual(refreshed.status_code, 200)
            self.assertEqual(
                self.client.session['doc_abbs'][0]['selected_description'],
                'thyroxine',
            )

    def test_document_url_requires_matching_django_session(self):
        with TemporaryDirectory() as media_root:
            session_id = 'test-session'
            path = Path(media_root) / f'{session_id}.docx'
            Document().save(path)

            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.get(f'/process/{session_id}/')

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse('upload_file'))


class TableGenerationViewTests(TestCase):
    def test_selected_abbreviation_is_exported_to_docx(self):
        session = self.client.session
        session['doc_abbs'] = [{
            'abbreviation': 'T4',
            'descriptions': ['thyroxine'],
            'selected_description': 'thyroxine',
        }]
        session.save()

        response = self.client.post('/make_abbreviation_table/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document',
        )
        self.assertIn(
            'attachment; filename=abbreviation_table.docx',
            response['Content-Disposition'],
        )

        document = Document(io.BytesIO(response.content))
        table = document.tables[0]

        self.assertEqual(table.rows[0].cells[0].text, 'Аббревиатура')
        self.assertEqual(table.rows[0].cells[1].text, 'Расшифровка')
        self.assertEqual(table.rows[1].cells[0].text, 'T4')
        self.assertEqual(table.rows[1].cells[1].text, 'Thyroxine')