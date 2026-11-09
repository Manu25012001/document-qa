import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from embeddings import GeminiService


class AnswerGenerationTests(unittest.TestCase):
    def test_uses_configured_chat_model_and_returns_text(self):
        service = GeminiService.__new__(GeminiService)
        service.generation_model = "gemini-3-flash-preview"
        send_message = Mock(return_value=SimpleNamespace(text="Answer [Page 2]"))
        create = Mock(return_value=SimpleNamespace(send_message=send_message))
        service.client = SimpleNamespace(chats=SimpleNamespace(create=create))

        answer = service.answer("What happened?", [
            {"page_start": 2, "text": "The event happened."}
        ])

        self.assertEqual(answer, "Answer [Page 2]")
        create_call = create.call_args.kwargs
        self.assertEqual(create_call["model"], "gemini-3-flash-preview")
        self.assertIn("untrusted data", create_call["config"].system_instruction)
        message = send_message.call_args.args[0]
        self.assertIn("What happened?", message)
        self.assertIn("The event happened.", message)

    def test_empty_model_response_is_rejected(self):
        service = GeminiService.__new__(GeminiService)
        service.generation_model = "gemini-3-flash-preview"
        service.client = SimpleNamespace(chats=SimpleNamespace(
            create=Mock(return_value=SimpleNamespace(
                send_message=Mock(return_value=SimpleNamespace(text="  "))))))
        with self.assertRaises(RuntimeError):
            service.answer("Question", [{"page_start": 1, "text": "Passage"}])


class EmbedBatchTests(unittest.TestCase):
    def test_embed_batch_groups_results(self):
        service = GeminiService.__new__(GeminiService)
        service.embedding_model = "gemini-embedding-001"
        mock_result = SimpleNamespace(embeddings=[
            SimpleNamespace(values=[0.1, 0.2]),
            SimpleNamespace(values=[0.3, 0.4]),
        ])
        service.client = SimpleNamespace(
            models=SimpleNamespace(embed_content=Mock(return_value=mock_result))
        )
        embeddings = service.embed_batch(["text1", "text2"], "RETRIEVAL_DOCUMENT")
        self.assertEqual(len(embeddings), 2)
        self.assertEqual(embeddings[0], [0.1, 0.2])
        self.assertEqual(embeddings[1], [0.3, 0.4])

    def test_embed_batch_empty_input(self):
        service = GeminiService.__new__(GeminiService)
        self.assertEqual(service.embed_batch([], "RETRIEVAL_DOCUMENT"), [])


if __name__ == "__main__":
    unittest.main()
