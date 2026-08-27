import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, TestCase

from abb_app.services.sessions import (
    DEMO_FILENAME,
    SESSION_FILE_KEY,
    cleanup_expired_documents,
)


class DocumentCleanupTests(SimpleTestCase):
    def test_cleanup_removes_only_expired_user_documents(self):
        with TemporaryDirectory() as media_root:
            expired = Path(media_root) / 'expired.docx'
            fresh = Path(media_root) / 'fresh.docx'
            demo = Path(media_root) / DEMO_FILENAME
            other = Path(media_root) / 'notes.txt'

            for path in (expired, fresh, demo, other):
                path.write_bytes(b'test')

            old_time = time.time() - 700
            for path in (expired, demo, other):
                os.utime(path, (old_time, old_time))

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


class DocumentSessionTests(TestCase):
    def test_touch_refreshes_session_and_only_touches_user_document(self):
        with TemporaryDirectory() as media_root:
            user_path = Path(media_root) / 'session.docx'
            demo_path = Path(media_root) / DEMO_FILENAME
            for path in (user_path, demo_path):
                path.write_bytes(b'test')

            old_time = time.time() - 700
            os.utime(user_path, (old_time, old_time))
            os.utime(demo_path, (old_time, old_time))
            demo_mtime = demo_path.stat().st_mtime

            with self.settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_SESSION_TIMEOUT_SECONDS=600,
            ):
                session = self.client.session
                session[SESSION_FILE_KEY] = user_path.name
                session.save()
                response = self.client.post('/session/touch/')
                self.assertEqual(response.status_code, 204)
                self.assertGreater(user_path.stat().st_mtime, old_time)

                session = self.client.session
                session[SESSION_FILE_KEY] = DEMO_FILENAME
                session.save()
                response = self.client.post('/session/touch/')
                expiry_age = self.client.session.get_expiry_age()

            self.assertEqual(response.status_code, 204)
            self.assertEqual(demo_path.stat().st_mtime, demo_mtime)
            self.assertGreaterEqual(expiry_age, 590)
            self.assertLessEqual(expiry_age, 600)
