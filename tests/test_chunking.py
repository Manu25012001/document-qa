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


if __name__ == "__main__":
    unittest.main()
