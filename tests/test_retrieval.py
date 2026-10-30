import unittest
from retrieval import cosine_similarity, retrieve


class RetrievalTests(unittest.TestCase):
    def test_cosine_similarity(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [2, 0]), 1.0)
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_zero_and_mismatched_vectors(self):
        self.assertEqual(cosine_similarity([0, 0], [1, 0]), 0.0)
        self.assertEqual(cosine_similarity([1], [1, 2]), 0.0)

    def test_relevant_chunks_are_ranked(self):
        chunks = [{"chunk_id": 1, "embedding": [1, 0]},
                  {"chunk_id": 2, "embedding": [0, 1]}]
        self.assertEqual(retrieve(chunks, [0.9, 0.1], 2)[0]["chunk_id"], 1)

    def test_empty_results(self):
        self.assertEqual(retrieve([], [1, 0]), [])
        self.assertEqual(retrieve([{"embedding": [1, 0]}], [1, 0], 0), [])


if __name__ == "__main__":
    unittest.main()
