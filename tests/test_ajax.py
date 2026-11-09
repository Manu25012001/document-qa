"""Unit tests verifying AJAX (X-Requested-With: XMLHttpRequest) endpoints."""
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO
from app import app, _documents


def _make_pdf_bytes(text="Sample content on page 1"):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


class AjaxEndpointTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        _documents.clear()

    def tearDown(self):
        _documents.clear()

    def test_ajax_upload_no_file(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "valid-token"

        res = self.client.post(
            "/upload",
            data={"csrf_token": "valid-token"},
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRF-Token": "valid-token"},
        )
        self.assertEqual(res.status_code, 400)
        json_data = res.get_json()
        self.assertFalse(json_data["success"])
        self.assertIn("Choose a PDF", json_data["error"])

    def test_ajax_upload_non_pdf(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "valid-token"

        data = {
            "csrf_token": "valid-token",
            "document": (BytesIO(b"fake txt content"), "test.txt"),
        }
        res = self.client.post(
            "/upload",
            data=data,
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRF-Token": "valid-token"},
        )
        self.assertEqual(res.status_code, 400)
        json_data = res.get_json()
        self.assertFalse(json_data["success"])
        self.assertIn(".pdf", json_data["error"])

    @patch("app._service")
    def test_ajax_upload_valid_pdf_success(self, mock_service_fn):
        mock_service = MagicMock()
        mock_service.embed_batch.return_value = [[0.1, 0.2, 0.3]]
        mock_service_fn.return_value = mock_service

        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "valid-token"

        pdf_bytes = _make_pdf_bytes("Hello from PDF")
        data = {
            "csrf_token": "valid-token",
            "document": (BytesIO(pdf_bytes), "sample.pdf"),
        }
        res = self.client.post(
            "/upload",
            data=data,
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRF-Token": "valid-token"},
        )
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data["success"])
        self.assertEqual(json_data["document"]["filename"], "sample.pdf")
        self.assertEqual(json_data["document"]["pages"], 1)

    def test_ajax_ask_no_document(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "valid-token"

        res = self.client.post(
            "/ask",
            data={"csrf_token": "valid-token", "question": "What is this?"},
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRF-Token": "valid-token"},
        )
        self.assertEqual(res.status_code, 410)
        json_data = res.get_json()
        self.assertFalse(json_data["success"])
        self.assertTrue(json_data["expired"])

    @patch("app._service")
    def test_ajax_ask_success(self, mock_service_fn):
        mock_service = MagicMock()
        mock_service.embed.return_value = [0.1, 0.2]
        mock_service.answer.return_value = "This is the answer from page 1."
        mock_service_fn.return_value = mock_service

        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "valid-token"
            sess["document_id"] = "doc-123"

        import time
        now = time.time()
        _documents["doc-123"] = {
            "filename": "demo.pdf",
            "pages": 1,
            "chunks": [
                {"chunk_id": 1, "page_start": 1, "page_end": 1, "text": "Sample text", "embedding": [0.1, 0.2]}
            ],
            "history": [],
            "created_at": now,
            "last_access": now,
        }

        res = self.client.post(
            "/ask",
            data={"csrf_token": "valid-token", "question": "What is the content?"},
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRF-Token": "valid-token"},
        )
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data["success"])
        self.assertEqual(json_data["answer"], "This is the answer from page 1.")
        self.assertEqual(json_data["sources"], [1])
        self.assertEqual(len(json_data["passages"]), 1)

    def test_ajax_reset_success(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "valid-token"
            sess["document_id"] = "doc-123"

        _documents["doc-123"] = {"filename": "demo.pdf"}

        res = self.client.post(
            "/reset",
            data={"csrf_token": "valid-token"},
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRF-Token": "valid-token"},
        )
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data["success"])
        self.assertNotIn("doc-123", _documents)


if __name__ == "__main__":
    unittest.main()
