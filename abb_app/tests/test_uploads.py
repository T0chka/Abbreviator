import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from docx import Document

from abb_app.uploads import UploadValidationError, validate_docx_upload


class UploadValidationTests(SimpleTestCase):
    def setUp(self):
        buffer = io.BytesIO()
        Document().save(buffer)
        self.docx_bytes = buffer.getvalue()

    def test_valid_docx_is_accepted(self):
        upload = SimpleUploadedFile('document.docx', self.docx_bytes)

        validate_docx_upload(upload)

    def test_wrong_extension_is_rejected(self):
        upload = SimpleUploadedFile('document.pdf', self.docx_bytes)

        with self.assertRaises(UploadValidationError):
            validate_docx_upload(upload)

    def test_invalid_docx_is_rejected(self):
        upload = SimpleUploadedFile('document.docx', b'not a docx')

        with self.assertRaises(UploadValidationError):
            validate_docx_upload(upload)

    def test_oversized_upload_returns_413(self):
        upload = SimpleUploadedFile('document.docx', b'12345')

        with self.settings(MAX_UPLOAD_SIZE=4, MAX_UPLOAD_SIZE_MB=0):
            with self.assertRaises(UploadValidationError) as context:
                validate_docx_upload(upload)

        self.assertEqual(context.exception.status_code, 413)