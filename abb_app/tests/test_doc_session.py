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


class DocumentSessionTests(TestCase):
    def test_touch_refreshes_file_and_django_session_expiry(self):
        with TemporaryDirectory() as media_root:
            filename = 'session.docx'
            path = Path(media_root) / filename
            path.write_bytes(b'test')
            old_time = time.time() - 700
            os.utime(path, (old_time, old_time))

            session = self.client.session
            session[SESSION_FILE_KEY] = filename
            session.save()

            with self.settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_SESSION_TIMEOUT_SECONDS=600,
            ):
                response = self.client.post('/session/touch/')
                expiry_age = self.client.session.get_expiry_age()

            self.assertEqual(response.status_code, 204)
            self.assertGreater(path.stat().st_mtime, old_time)
            self.assertGreaterEqual(expiry_age, 590)
            self.assertLessEqual(expiry_age, 600)

    def test_demo_touch_expires_session_without_touching_demo_file(self):
        with TemporaryDirectory() as media_root:
            path = Path(media_root) / DEMO_FILENAME
            path.write_bytes(b'test')
            old_time = time.time() - 700
            os.utime(path, (old_time, old_time))
            mtime_before = path.stat().st_mtime

            session = self.client.session
            session[SESSION_FILE_KEY] = DEMO_FILENAME
            session.save()

            with self.settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_SESSION_TIMEOUT_SECONDS=600,
            ):
                response = self.client.post('/session/touch/')
                expiry_age = self.client.session.get_expiry_age()

            self.assertEqual(response.status_code, 204)
            self.assertEqual(path.stat().st_mtime, mtime_before)
            self.assertGreaterEqual(expiry_age, 590)
            self.assertLessEqual(expiry_age, 600)
