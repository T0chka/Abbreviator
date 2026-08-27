import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from docx import Document

from abb_app.models import AbbreviationEntry
from abb_app.services.sessions import (
    PROCESSED_FILE_SESSION_KEY,
    SESSION_FILE_KEY,
    TABLE_CHECK_SESSION_KEY,
    WORKFLOW_STATE_SESSION_KEY,
)


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
            self.assertContains(refreshed, 'data-selected="true"')

    def test_refresh_preserves_table_check_choice(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                with TemporaryDirectory() as media_root:
                    session_id = f'table-check-{str(enabled).lower()}'
                    path = Path(media_root) / f'{session_id}.docx'
                    Document().save(path)

                    session = self.client.session
                    session[SESSION_FILE_KEY] = path.name
                    session[PROCESSED_FILE_SESSION_KEY] = path.name
                    session['doc_abbs'] = []
                    session['initial_abbs'] = [{
                        'abbreviation': 'T4',
                        'description': 'thyroxine',
                    }]
                    session.pop(TABLE_CHECK_SESSION_KEY, None)
                    session.save()

                    with self.settings(
                        MEDIA_ROOT=media_root,
                        DOCUMENT_SESSION_TIMEOUT_SECONDS=600,
                    ):
                        first = self.client.get(
                            reverse(
                                'process_file_with_session',
                                args=[session_id],
                            )
                        )
                        update = self.client.post(
                            reverse('update_table_check'),
                            data=json.dumps({'enabled': enabled}),
                            content_type='application/json',
                        )
                        refreshed = self.client.get(
                            reverse(
                                'process_file_with_session',
                                args=[session_id],
                            )
                        )

                    self.assertContains(first, 'id="table-check-dialog"')
                    self.assertEqual(update.status_code, 200)
                    self.assertNotContains(
                        refreshed,
                        'id="table-check-dialog"',
                    )
                    self.assertEqual(
                        self.client.session[TABLE_CHECK_SESSION_KEY],
                        enabled,
                    )
                    self.assertEqual(
                        refreshed.context['table_check_enabled'],
                        enabled,
                    )

    def test_new_upload_resets_table_check_choice(self):
        buffer = io.BytesIO()
        Document().save(buffer)
        upload = SimpleUploadedFile('new.docx', buffer.getvalue())

        session = self.client.session
        session[TABLE_CHECK_SESSION_KEY] = True
        session[WORKFLOW_STATE_SESSION_KEY] = {
            'comparison-block': True,
            'table-preview-tool': True,
        }
        session[PROCESSED_FILE_SESSION_KEY] = 'old.docx'
        session['doc_abbs'] = [{'abbreviation': 'OLD'}]
        session['initial_abbs'] = [{'abbreviation': 'OLD'}]
        session.save()

        with TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('upload_file'),
                    {'uploaded_file': upload},
                )

        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertNotIn(TABLE_CHECK_SESSION_KEY, session)
        self.assertNotIn(WORKFLOW_STATE_SESSION_KEY, session)
        self.assertNotIn(PROCESSED_FILE_SESSION_KEY, session)
        self.assertNotIn('doc_abbs', session)
        self.assertNotIn('initial_abbs', session)

    def test_refresh_preserves_expanded_workflow_tools(self):
        with TemporaryDirectory() as media_root:
            session_id = 'workflow-state'
            path = Path(media_root) / f'{session_id}.docx'
            Document().save(path)

            session = self.client.session
            session[SESSION_FILE_KEY] = path.name
            session[PROCESSED_FILE_SESSION_KEY] = path.name
            session['doc_abbs'] = []
            session['initial_abbs'] = [{
                'abbreviation': 'T4',
                'description': 'thyroxine',
            }]
            session[TABLE_CHECK_SESSION_KEY] = True
            session.save()

            with self.settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_SESSION_TIMEOUT_SECONDS=600,
            ):
                sizes = {
                    'comparison-block': 240,
                    'table-preview-tool': 320,
                }
                for tool_id, height in sizes.items():
                    update = self.client.post(
                        reverse('update_workflow_state'),
                        data=json.dumps({
                            'tool_id': tool_id,
                            'open': True,
                            'height': height,
                        }),
                        content_type='application/json',
                    )
                    self.assertEqual(update.status_code, 200)

                refreshed = self.client.get(
                    reverse(
                        'process_file_with_session',
                        args=[session_id],
                    )
                )

            self.assertEqual(refreshed.status_code, 200)
            self.assertTrue(refreshed.context['comparison_open'])
            self.assertEqual(refreshed.context['comparison_height'], 240)
            self.assertTrue(refreshed.context['table_preview_open'])
            self.assertEqual(refreshed.context['table_preview_height'], 320)
            html = refreshed.content.decode()
            self.assertRegex(
                html,
                r'<details id="comparison-block"[^>]*\bopen\b',
            )
            self.assertRegex(
                html,
                r'<details id="table-preview-tool"[^>]*\bopen\b',
            )
            self.assertIn('style="height: 240px;"', html)
            self.assertIn('style="height: 320px;"', html)

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