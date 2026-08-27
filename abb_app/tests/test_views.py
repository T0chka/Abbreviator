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
    CARD_STATE_SESSION_KEY,
    DEMO_FILENAME,
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

            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.get(
                    reverse('process_file_with_session', args=[session_id])
                )

            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'content.html')
            doc_abbs = self.client.session['doc_abbs']
            self.assertEqual(len(doc_abbs), 1)
            self.assertEqual(doc_abbs[0]['abbreviation'], 'T4')
            self.assertEqual(doc_abbs[0]['descriptions'], ['thyroxine'])
            self.assertEqual(
                self.client.session[PROCESSED_FILE_SESSION_KEY],
                path.name,
            )

    def test_refresh_preserves_review_card_and_comparison_state(self):
        AbbreviationEntry.objects.create(
            abbreviation='T4',
            description='thyroxine',
            status='approved',
        )

        with TemporaryDirectory() as media_root:
            session_id = 'review-state'
            path = Path(media_root) / f'{session_id}.docx'
            doc = Document()
            doc.add_paragraph('У пациента определяли уровень T4.')
            doc.save(path)

            session = self.client.session
            session[SESSION_FILE_KEY] = path.name
            session.save()

            with self.settings(MEDIA_ROOT=media_root):
                self.client.get(
                    reverse('process_file_with_session', args=[session_id])
                )
                session = self.client.session
                session['initial_abbs'] = [{
                    'abbreviation': 'T4',
                    'descriptions': ['thyroxine'],
                }]
                session[TABLE_CHECK_SESSION_KEY] = True
                session.save()

                before_review = self.client.get(
                    reverse('process_file_with_session', args=[session_id])
                )
                update = self.client.post(
                    reverse('update_abbreviation'),
                    data=json.dumps({
                        'abbreviation': 'T4',
                        'description': 'thyroxine',
                        'action': 'add',
                    }),
                    content_type='application/json',
                )
                refreshed = self.client.get(
                    reverse('process_file_with_session', args=[session_id])
                )

            self.assertTrue(
                before_review.context['comparison_context'][
                    'waiting_for_review'
                ]
            )
            self.assertEqual(update.status_code, 200)
            entry = self.client.session['doc_abbs'][0]
            self.assertEqual(entry['selected_description'], 'thyroxine')
            self.assertTrue(entry['reviewed'])
            self.assertIn(
                'T4',
                self.client.session[CARD_STATE_SESSION_KEY],
            )
            self.assertIn(
                'T4',
                refreshed.context['collapsed_abbreviations'],
            )
            self.assertNotIn(
                'waiting_for_review',
                refreshed.context['comparison_context'],
            )

    def test_refresh_preserves_skipped_and_manual_card_state(self):
        with TemporaryDirectory() as media_root:
            session_id = 'card-state'
            path = Path(media_root) / f'{session_id}.docx'
            Document().save(path)

            session = self.client.session
            session[SESSION_FILE_KEY] = path.name
            session[PROCESSED_FILE_SESSION_KEY] = path.name
            session['doc_abbs'] = [
                {
                    'abbreviation': 'T4',
                    'descriptions': ['thyroxine'],
                    'selected_description': None,
                    'reviewed': False,
                },
                {
                    'abbreviation': 'ABC',
                    'descriptions': [],
                    'selected_description': None,
                    'reviewed': False,
                },
            ]
            session['initial_abbs'] = []
            session.save()

            with self.settings(MEDIA_ROOT=media_root):
                skipped = self.client.post(
                    reverse('update_abbreviation'),
                    data=json.dumps({
                        'abbreviation': 'T4',
                        'action': 'skip',
                    }),
                    content_type='application/json',
                )
                collapsed = self.client.post(
                    reverse('update_card_state'),
                    data=json.dumps({
                        'abbreviation': 'ABC',
                        'collapsed': True,
                    }),
                    content_type='application/json',
                )
                refreshed = self.client.get(
                    reverse('process_file_with_session', args=[session_id])
                )

            self.assertEqual(skipped.status_code, 200)
            self.assertEqual(collapsed.status_code, 200)
            entries = {
                item['abbreviation']: item
                for item in self.client.session['doc_abbs']
            }
            self.assertTrue(entries['T4']['reviewed'])
            self.assertIsNone(entries['T4']['selected_description'])
            self.assertEqual(
                refreshed.context['collapsed_abbreviations'],
                {'T4', 'ABC'},
            )
            self.assertContains(refreshed, '- (убрано)')

    def test_refresh_preserves_table_choice_and_workflow_layout(self):
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
            session.save()

            with self.settings(MEDIA_ROOT=media_root):
                first = self.client.get(
                    reverse('process_file_with_session', args=[session_id])
                )
                disabled = self.client.post(
                    reverse('update_table_check'),
                    data=json.dumps({'enabled': False}),
                    content_type='application/json',
                )
                disabled_refresh = self.client.get(
                    reverse('process_file_with_session', args=[session_id])
                )
                enabled = self.client.post(
                    reverse('update_table_check'),
                    data=json.dumps({'enabled': True}),
                    content_type='application/json',
                )

                sizes = {
                    'comparison-block': 240,
                    'table-preview-tool': 320,
                }
                for tool_id, height in sizes.items():
                    response = self.client.post(
                        reverse('update_workflow_state'),
                        data=json.dumps({
                            'tool_id': tool_id,
                            'open': True,
                            'height': height,
                        }),
                        content_type='application/json',
                    )
                    self.assertEqual(response.status_code, 200)

                refreshed = self.client.get(
                    reverse('process_file_with_session', args=[session_id])
                )

            self.assertContains(first, 'id="table-check-dialog"')
            self.assertEqual(disabled.status_code, 200)
            self.assertFalse(disabled_refresh.context['table_check_enabled'])
            self.assertNotContains(
                disabled_refresh,
                'id="table-check-dialog"',
            )
            self.assertEqual(enabled.status_code, 200)
            self.assertTrue(refreshed.context['table_check_enabled'])
            self.assertTrue(refreshed.context['comparison_open'])
            self.assertEqual(refreshed.context['comparison_height'], 240)
            self.assertTrue(refreshed.context['table_preview_open'])
            self.assertEqual(refreshed.context['table_preview_height'], 320)
            html = refreshed.content.decode()
            self.assertIn('style="height: 240px;"', html)
            self.assertIn('style="height: 320px;"', html)

    def test_new_upload_resets_processing_state(self):
        buffer = io.BytesIO()
        Document().save(buffer)
        upload = SimpleUploadedFile('new.docx', buffer.getvalue())

        session = self.client.session
        session[TABLE_CHECK_SESSION_KEY] = True
        session[CARD_STATE_SESSION_KEY] = ['OLD']
        session[WORKFLOW_STATE_SESSION_KEY] = {
            'comparison-block': {'open': True, 'height': 240},
            'table-preview-tool': {'open': True, 'height': 320},
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
        for key in (
            TABLE_CHECK_SESSION_KEY,
            WORKFLOW_STATE_SESSION_KEY,
            CARD_STATE_SESSION_KEY,
            PROCESSED_FILE_SESSION_KEY,
            'doc_abbs',
            'initial_abbs',
        ):
            with self.subTest(key=key):
                self.assertNotIn(key, session)

    def test_demo_refresh_starts_from_clean_processing_state(self):
        AbbreviationEntry.objects.create(
            abbreviation='T4',
            description='thyroxine',
            status='approved',
        )

        with TemporaryDirectory() as media_root:
            path = Path(media_root) / DEMO_FILENAME
            doc = Document()
            doc.add_paragraph('T4')
            doc.save(path)

            session = self.client.session
            session[SESSION_FILE_KEY] = DEMO_FILENAME
            session[PROCESSED_FILE_SESSION_KEY] = DEMO_FILENAME
            session['doc_abbs'] = [{
                'abbreviation': 'OLD',
                'selected_description': 'old',
                'reviewed': True,
            }]
            session['initial_abbs'] = [{'abbreviation': 'OLD'}]
            session[TABLE_CHECK_SESSION_KEY] = False
            session[CARD_STATE_SESSION_KEY] = ['OLD']
            session[WORKFLOW_STATE_SESSION_KEY] = {
                'comparison-block': {'open': True, 'height': 240},
            }
            session.save()

            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.get(
                    reverse('process_file_with_session', args=['test_drive'])
                )

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['is_demo'])
            self.assertTrue(response.context['table_check_enabled'])
            self.assertEqual(response.context['collapsed_abbreviations'], set())
            self.assertFalse(response.context['comparison_open'])
            self.assertNotIn(TABLE_CHECK_SESSION_KEY, self.client.session)
            self.assertNotIn(WORKFLOW_STATE_SESSION_KEY, self.client.session)
            self.assertEqual(
                [entry['abbreviation'] for entry in self.client.session['doc_abbs']],
                ['T4'],
            )
            self.assertIsNone(
                self.client.session['doc_abbs'][0]['selected_description']
            )

    def test_document_url_requires_matching_django_session(self):
        with TemporaryDirectory() as media_root:
            session_id = 'test-session'
            path = Path(media_root) / f'{session_id}.docx'
            Document().save(path)

            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.get(
                    reverse('process_file_with_session', args=[session_id])
                )

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse('upload_file'))
