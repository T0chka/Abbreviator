import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from docx import Document

from abb_app.services.uploads import UploadValidationError, validate_docx_upload


class UploadValidationTests(SimpleTestCase):
    def test_invalid_uploads_are_rejected(self):
        valid_buffer = io.BytesIO()
        Document().save(valid_buffer)
        cases = [
            (
                SimpleUploadedFile('document.txt', valid_buffer.getvalue()),
                {},
                400,
            ),
            (
                SimpleUploadedFile('document.docx', b'not-a-docx'),
                {},
                400,
            ),
            (
                SimpleUploadedFile('large.docx', valid_buffer.getvalue()),
                {'MAX_UPLOAD_SIZE': 4, 'MAX_UPLOAD_SIZE_MB': 0},
                413,
            ),
        ]

        for upload, settings, expected_status in cases:
            with self.subTest(name=upload.name, status=expected_status):
                with self.settings(**settings):
                    with self.assertRaises(UploadValidationError) as context:
                        validate_docx_upload(upload)
                self.assertEqual(
                    context.exception.status_code,
                    expected_status,
                )
