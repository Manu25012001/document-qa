import unittest
from document_processor import chunk_pages


class ChunkingTests(unittest.TestCase):
    def test_chunks_cover_text_and_keep_page(self):
        chunks = chunk_pages([(7, "abcdefghij")], chunk_size=4, overlap=1)
        self.assertEqual([c.page_start for c in chunks], [7, 7, 7])
        self.assertEqual([c.text for c in chunks], ["abcd", "defg", "ghij"])

    def test_overlap_is_preserved(self):
        chunks = chunk_pages([(1, "abcdefgh")], chunk_size=5, overlap=2)
        self.assertTrue(chunks[0].text[-2:] == chunks[1].text[:2])

    def test_empty_input(self):
        self.assertEqual(chunk_pages([], 10, 2), [])
        self.assertEqual(chunk_pages([(1, "   ")], 10, 2), [])

    def test_invalid_overlap(self):
        with self.assertRaises(ValueError):
            chunk_pages([(1, "text")], 5, 5)

    def test_cross_page_chunks(self):
        """Chunks should span page boundaries when text flows across pages."""
        pages = [(1, "aaaa bbbb"), (2, "cccc dddd")]
        # Combined: "aaaa bbbb cccc dddd" (19 chars)
        # chunk_size=12 should produce a chunk spanning pages 1 and 2.
        chunks = chunk_pages(pages, chunk_size=12, overlap=3)
        has_cross_page = any(c.page_start != c.page_end for c in chunks)
        self.assertTrue(has_cross_page, "Expected at least one chunk spanning two pages")

    def test_page_end_tracks_last_page(self):
        """page_end should equal page_start for single-page text."""
        chunks = chunk_pages([(5, "hello world")], chunk_size=100, overlap=0)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].page_start, 5)
        self.assertEqual(chunks[0].page_end, 5)

    def test_multiple_pages_single_chunk(self):
        """A small multi-page document that fits in one chunk should span all pages."""
        pages = [(1, "ab"), (2, "cd"), (3, "ef")]
        chunks = chunk_pages(pages, chunk_size=100, overlap=0)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].page_start, 1)
        self.assertEqual(chunks[0].page_end, 3)
        self.assertEqual(chunks[0].text, "ab cd ef")


if __name__ == "__main__":
    unittest.main()
