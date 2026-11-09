import unittest
from document_processor import extract_pages


def _make_pdf(text: str = "Hello world", num_pages: int = 1) -> bytes:
    """Create a minimal PDF in memory using PyMuPDF."""
    import pymupdf
    doc = pymupdf.open()
    for _ in range(num_pages):
        page = doc.new_page()
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


class ExtractPagesTests(unittest.TestCase):
    def test_basic_extraction(self):
        pdf = _make_pdf("Test content", num_pages=2)
        pages = extract_pages(pdf)
        self.assertEqual(len(pages), 2)
        for page_num, text in pages:
            self.assertIn("Test content", text)

    def test_page_numbers_start_at_one(self):
        pdf = _make_pdf("Page text", num_pages=3)
        pages = extract_pages(pdf)
        self.assertEqual([n for n, _ in pages], [1, 2, 3])

    def test_empty_bytes_raises(self):
        with self.assertRaises(ValueError) as ctx:
            extract_pages(b"")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_invalid_data_raises(self):
        with self.assertRaises(ValueError) as ctx:
            extract_pages(b"not a pdf at all")
        self.assertIn("valid PDF", str(ctx.exception))

    def test_page_limit_enforced(self):
        pdf = _make_pdf("text", num_pages=5)
        with self.assertRaises(ValueError) as ctx:
            extract_pages(pdf, max_pages=3)
        self.assertIn("3-page", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
