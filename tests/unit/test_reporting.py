import unittest
from pathlib import Path
import tempfile
import shutil
import os
from src.harness.reporting import MasterReport

class TestMasterReport(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.report_path = self.test_dir / "harness_audit_master_report.md"
        self.reporting = MasterReport(self.report_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_init_report(self):
        self.reporting.init_report("gemini-2.5-flash-lite")
        content = self.report_path.read_text()
        self.assertIn("# Harness Audit Master Report", content)
        self.assertIn("gemini-2.5-flash-lite", content)
        self.assertIn("Audit Timestamp", content)

    def test_add_section(self):
        self.reporting.init_report("gemini-2.5-flash-lite")
        self.reporting.add_section("Section 1: Logic & Snapshots", "All tests passed!")
        content = self.report_path.read_text()
        self.assertIn("## Section 1: Logic & Snapshots", content)
        self.assertIn("All tests passed!", content)

    def test_update_section(self):
        self.reporting.init_report("gemini-2.5-flash-lite")
        self.reporting.add_section("Section 1", "Initial content")
        self.reporting.add_section("Section 1", "Updated content")
        content = self.report_path.read_text()
        self.assertIn("Updated content", content)
        self.assertNotIn("Initial content", content)

    def test_multiple_sections(self):
        self.reporting.init_report("gemini-2.5-flash-lite")
        self.reporting.add_section("Section 1", "Content 1")
        self.reporting.add_section("Section 2", "Content 2")
        content = self.report_path.read_text()
        self.assertIn("## Section 1", content)
        self.assertIn("Content 1", content)
        self.assertIn("## Section 2", content)
        self.assertIn("Content 2", content)

if __name__ == "__main__":
    unittest.main()
