"""
Smoke tests for Scribe server endpoints.
Tests /save, /save-dir, /job/<id> without requiring the Whisper model.
"""
import os
import sys
import json
import uuid
import tempfile
import shutil

# Patch out the WhisperModel import before importing server
import unittest
from unittest.mock import MagicMock, patch

# Mock faster_whisper before server.py tries to load the model
sys.modules['faster_whisper'] = MagicMock()

with patch.dict(os.environ):
    import server

# Point SAVE_DIR to a temp directory for testing
TEST_DIR = tempfile.mkdtemp(prefix="scribe_test_")
server.SAVE_DIR = TEST_DIR


class TestSaveDir(unittest.TestCase):
    def setUp(self):
        self.app = server.app.test_client()

    def test_get_save_dir(self):
        res = self.app.get('/save-dir')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn('directory', data)
        self.assertEqual(data['directory'], TEST_DIR)


class TestSave(unittest.TestCase):
    def setUp(self):
        self.app = server.app.test_client()

    def test_save_with_defaults(self):
        res = self.app.post('/save',
            data=json.dumps({"text": "Hello world"}),
            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['file'].startswith('transcript_'))
        self.assertTrue(data['file'].endswith('.txt'))
        # Verify file exists on disk
        self.assertTrue(os.path.exists(data['path']))
        with open(data['path'], 'r') as f:
            self.assertEqual(f.read(), "Hello world")

    def test_save_with_custom_filename(self):
        res = self.app.post('/save',
            data=json.dumps({"text": "Custom name test", "filename": "my_transcript"}),
            content_type='application/json')
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['file'], 'my_transcript.txt')

    def test_save_with_custom_directory(self):
        custom_dir = os.path.join(TEST_DIR, "custom_subdir")
        res = self.app.post('/save',
            data=json.dumps({
                "text": "Dir test",
                "filename": "dir_test.txt",
                "directory": custom_dir
            }),
            content_type='application/json')
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'success')
        self.assertTrue(os.path.exists(os.path.join(custom_dir, "dir_test.txt")))

    def test_save_preserves_txt_extension(self):
        res = self.app.post('/save',
            data=json.dumps({"text": "ext test", "filename": "already.txt"}),
            content_type='application/json')
        data = json.loads(res.data)
        self.assertEqual(data['file'], 'already.txt')

    def test_save_no_text_returns_400(self):
        res = self.app.post('/save',
            data=json.dumps({"filename": "no_text"}),
            content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_save_options_cors(self):
        res = self.app.options('/save')
        self.assertEqual(res.status_code, 200)


class TestJobRecovery(unittest.TestCase):
    def setUp(self):
        self.app = server.app.test_client()

    def test_get_nonexistent_job_returns_404(self):
        res = self.app.get('/job/nonexistent-id')
        self.assertEqual(res.status_code, 404)

    def test_get_existing_job(self):
        job_id = str(uuid.uuid4())
        server.jobs[job_id] = {
            "segments": [
                {"text": "Hello", "index": 0, "percent": 50, "start": 0.0, "end": 5.0},
                {"text": "world", "index": 1, "percent": 100, "start": 5.0, "end": 10.0},
            ],
            "status": "done",
            "full_text": "Hello world",
            "url": "https://youtube.com/watch?v=test",
            "error": None,
        }

        res = self.app.get(f'/job/{job_id}')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)

        self.assertEqual(data['job_id'], job_id)
        self.assertEqual(data['status'], 'done')
        self.assertEqual(len(data['segments']), 2)
        self.assertEqual(data['full_text'], 'Hello world')
        self.assertEqual(data['url'], 'https://youtube.com/watch?v=test')
        self.assertIsNone(data['error'])

    def test_get_running_job(self):
        job_id = str(uuid.uuid4())
        server.jobs[job_id] = {
            "segments": [
                {"text": "partial", "index": 0, "percent": 30, "start": 0.0, "end": 3.0},
            ],
            "status": "running",
            "full_text": "partial",
            "url": "https://youtube.com/watch?v=running",
            "error": None,
        }

        res = self.app.get(f'/job/{job_id}')
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'running')
        self.assertEqual(len(data['segments']), 1)

    def test_get_errored_job(self):
        job_id = str(uuid.uuid4())
        server.jobs[job_id] = {
            "segments": [],
            "status": "error",
            "full_text": "",
            "url": "https://youtube.com/watch?v=fail",
            "error": "yt-dlp failed",
        }

        res = self.app.get(f'/job/{job_id}')
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['error'], 'yt-dlp failed')


class TestServeIndex(unittest.TestCase):
    def setUp(self):
        self.app = server.app.test_client()

    def test_index_returns_html(self):
        res = self.app.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Syntra Transcriber', res.data)
        # Check new UI elements exist
        self.assertIn(b'restoreBanner', res.data)
        self.assertIn(b'saveModal', res.data)
        self.assertIn(b'saveDraft', res.data)
        self.assertIn(b'openSaveModal', res.data)


def cleanup():
    shutil.rmtree(TEST_DIR, ignore_errors=True)


if __name__ == '__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        cleanup()
