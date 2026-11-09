"""Flask test-client tests for the app routes."""
import unittest
from unittest.mock import patch, MagicMock
from app import app, _documents


def _make_pdf_bytes():
    """Create a tiny valid PDF for upload tests."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Sample document text for testing.")
    data = doc.tobytes()
    doc.close()
    return data


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        _documents.clear()

    def tearDown(self):
        _documents.clear()

    def test_index_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Document", response.data)

    def test_favicon_returns_204(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 204)

    def test_upload_no_file_flashes_error(self):
        # First get a CSRF token
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf-token"
        response = self.client.post("/upload", data={"csrf_token": "test-csrf-token"},
                                    follow_redirects=True)
        self.assertIn(b"Choose a PDF", response.data)

    def test_upload_non_pdf_rejected(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf-token"
        from io import BytesIO
        data = {"csrf_token": "test-csrf-token",
                "document": (BytesIO(b"not a pdf"), "readme.txt")}
        response = self.client.post("/upload", data=data,
                                    content_type="multipart/form-data",
                                    follow_redirects=True)
        self.assertIn(b".pdf", response.data)

    def test_csrf_rejection(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "real-token"
        response = self.client.post("/upload",
                                    data={"csrf_token": "wrong-token"},
                                    follow_redirects=True)
        self.assertIn(b"expired", response.data)

    def test_ask_without_document_redirects(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf-token"
        response = self.client.post("/ask",
                                    data={"csrf_token": "test-csrf-token",
                                          "question": "What?"},
                                    follow_redirects=True)
        self.assertIn(b"Upload", response.data)

    def test_reset_clears_state(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf-token"
            sess["document_id"] = "fake-id"
        _documents["fake-id"] = {"filename": "test.pdf", "pages": 1,
                                 "chunks": [], "history": [],
                                 "created_at": 0, "last_access": 0}
        response = self.client.post("/reset",
                                    data={"csrf_token": "test-csrf-token"},
                                    follow_redirects=True)
        self.assertIn(b"cleared", response.data)
        self.assertNotIn("fake-id", _documents)


if __name__ == "__main__":
    unittest.main()
