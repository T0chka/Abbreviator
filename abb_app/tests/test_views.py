import io
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase
from docx import Document

from abb_app.models import AbbreviationEntry


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

            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.get(f'/process/{session_id}/')

            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'content.html')

            doc_abbs = self.client.session['doc_abbs']
            self.assertEqual(len(doc_abbs), 1)
            self.assertEqual(doc_abbs[0]['abbreviation'], 'T4')
            self.assertEqual(doc_abbs[0]['descriptions'], ['thyroxine'])


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