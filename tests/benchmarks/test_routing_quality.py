import pytest
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.models.base_model import DeepEvalBaseLLM
from harness.discovery_engine import query_llm
from harness.dispatcher import OrchestratorDispatcher
from harness.reporting import default_report
import os
import tempfile
from pathlib import Path

# Custom Gemini wrapper for DeepEval to avoid Client init issues
class CustomGemini(DeepEvalBaseLLM):
    def __init__(self, model_name="gemini-2.5-flash-lite"):
        self.model_name = model_name

    def load_model(self):
        return self.model_name

    def generate(self, prompt: str) -> str:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        return query_llm(prompt, "gemini", api_key, model=self.model_name)

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self):
        return self.model_name

custom_gemini = CustomGemini()

@pytest.mark.parametrize(
    "input_text, expected_branch",
    [
        ("I want to change how the app works.", "Branch B"),
        ("There is a typo in the README.", "Branch D"),
        ("The tests are failing with a NameError.", "Branch A"),
    ]
)
def test_routing_justification(input_text, expected_branch):
    # This test uses LLM-as-a-judge to evaluate if the Orchestrator's
    # REAL justification for a route is high quality.
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # We need a dummy DB file for dispatcher
        dispatcher = OrchestratorDispatcher(tmp_dir)
        
        # Use real classification logic
        result = dispatcher.classify_intent(input_text)
        actual_branch = f"Branch {result['branch']}"
        actual_output = result['justification']
    
    metric = GEval(
        name="Routing Relevance",
        criteria="Does the justification (Chain of Thought) logically explain why the chosen branch is appropriate for the input?",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=custom_gemini
    )
    
    test_case = LLMTestCase(
        input=input_text,
        actual_output=actual_output
    )
    
    metric.measure(test_case)
    
    # Record result in Section 5
    score = float(metric.score)
    reason = metric.reason.replace('\n', ' ') if hasattr(metric, 'reason') and metric.reason else 'N/A'
    # Clean up justification for table
    display_justification = actual_output.replace('|', '\\|').replace('\n', ' ')
    result_line = f"| {input_text} | {expected_branch} | {actual_branch} | {display_justification} | {score:.2f} | {reason} |"
    
    section_title = "Section 5: Quality Metrics (DeepEval)"
    table_header = "| Input | Expected | Actual | Actual Justification (Chain of Thought) | Score | Reason |\n| --- | --- | --- | --- | --- | --- |"
    
    import re
    if default_report.report_path.exists():
        content = default_report.report_path.read_text()
        pattern = rf"## {re.escape(section_title)}\n\n(.*?)(?=\n## |\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            existing_table = match.group(1).strip()
            if table_header in existing_table:
                new_table = existing_table + "\n" + result_line
                default_report.add_section(section_title, new_table)
            else:
                default_report.add_section(section_title, table_header + "\n" + result_line)
        else:
            default_report.add_section(section_title, table_header + "\n" + result_line)
    else:
        default_report.add_section(section_title, table_header + "\n" + result_line)

    assert actual_branch == expected_branch
    assert metric.score >= 0.1
