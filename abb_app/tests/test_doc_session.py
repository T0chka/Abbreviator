import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from abb_app.document_session import (
    DEMO_FILENAME,
    cleanup_expired_documents,
)


class DocumentCleanupTests(SimpleTestCase):
    def test_cleanup_removes_only_expired_documents(self):
        with TemporaryDirectory() as media_root:
            expired = Path(media_root) / 'expired.docx'
            fresh = Path(media_root) / 'fresh.docx'
            demo = Path(media_root) / DEMO_FILENAME
            other = Path(media_root) / 'notes.txt'

            for path in (expired, fresh, demo, other):
                path.write_bytes(b'test')

            old_time = time.time() - 700
            os.utime(expired, (old_time, old_time))
            os.utime(demo, (old_time, old_time))
            os.utime(other, (old_time, old_time))

            with self.settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_SESSION_TIMEOUT_SECONDS=600,
            ):
                deleted = cleanup_expired_documents()

            self.assertEqual(deleted, 1)
            self.assertFalse(expired.exists())
            self.assertTrue(fresh.exists())
            self.assertTrue(demo.exists())
            self.assertTrue(other.exists())