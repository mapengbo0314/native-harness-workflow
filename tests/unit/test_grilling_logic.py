import unittest
from unittest.mock import MagicMock, patch
import json
from src.harness.init.discovery_engine import generate_grilling_questions, synthesize_grilled_context

class TestGrillingLogic(unittest.TestCase):
    def setUp(self):
        self.project_path = "/tmp/test_project"
        self.llm_provider = "gemini"
        self.api_key = "fake_key"

    @patch("src.harness.init.discovery_engine.get_file_tree_summary")
    @patch("src.harness.init.discovery_engine.get_symbol_census")
    def test_generate_grilling_questions_success(self, mock_census, mock_tree):
        mock_tree.return_value = "src/\n  main.py"
        mock_census.return_value = ["@app.route", "import flask"]
        
        mock_query_llm = MagicMock()
        mock_query_llm.return_value = json.dumps([
            {"question": "Is this a Flask app?", "multiple_choice_options": ["Yes", "No"]},
            {"question": "What is the domain?", "multiple_choice_options": ["Fintech", "E-commerce"]}
        ])
        
        questions = generate_grilling_questions(
            self.project_path, mock_query_llm, self.llm_provider, self.api_key
        )
        
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]["question"], "Is this a Flask app?")
        self.assertIn("Yes", questions[0]["multiple_choice_options"])

    @patch("src.harness.init.discovery_engine.get_file_tree_summary")
    @patch("src.harness.init.discovery_engine.get_symbol_census")
    def test_generate_grilling_questions_fallback(self, mock_census, mock_tree):
        mock_tree.return_value = "src/\n  main.py"
        mock_census.return_value = []
        
        mock_query_llm = MagicMock()
        mock_query_llm.return_value = "Invalid JSON"
        
        questions = generate_grilling_questions(
            self.project_path, mock_query_llm, self.llm_provider, self.api_key
        )
        
        # Should fallback to 3 static questions
        self.assertEqual(len(questions), 3)
        self.assertTrue(any("purpose" in q["question"].lower() for q in questions))

    def test_synthesize_grilled_context(self):
        qa_pairs = [
            ("Is this a Flask app?", "Yes"),
            ("What is the domain?", "Fintech")
        ]
        
        mock_query_llm = MagicMock()
        mock_query_llm.return_value = "# Project Context\n\n## Purpose\nA Fintech Flask app."
        
        content = synthesize_grilled_context(
            self.project_path, qa_pairs, mock_query_llm, self.llm_provider, self.api_key
        )
        
        self.assertIn("# Project Context", content)
        self.assertIn("Fintech", content)

if __name__ == "__main__":
    unittest.main()
