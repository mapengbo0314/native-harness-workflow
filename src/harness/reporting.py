import datetime
from pathlib import Path
import re

class MasterReport:
    def __init__(self, report_path: Path = None):
        if report_path is None:
            # Default path relative to project root
            self.report_path = Path("artifacts/harness_audit_master_report.md")
        else:
            self.report_path = report_path

    def init_report(self, model_name: str):
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"""# Harness Audit Master Report

**Audit Timestamp:** {timestamp}
**Model Used:** {model_name}

---

"""
        self.report_path.write_text(header)

    def add_section(self, title: str, content: str):
        if not self.report_path.exists():
            self.init_report("Unknown Model")

        current_content = self.report_path.read_text()
        
        # Ensure we match exactly the section header "## Title" and not something like "### Title"
        # and capture until the next "## " at the start of a line.
        section_pattern = rf"(^|\n)## {re.escape(title)}\n.*?(?=(\n## |\Z))"
        section_text = f"\n## {title}\n\n{content.strip()}\n"
        
        if re.search(section_pattern, current_content, re.DOTALL | re.MULTILINE):
            # Replace existing section
            new_content = re.sub(section_pattern, section_text, current_content, flags=re.DOTALL | re.MULTILINE)
            # Ensure proper spacing
            if not new_content.endswith("\n\n"):
                new_content = new_content.rstrip() + "\n\n"
            self.report_path.write_text(new_content)
        else:
            # Append new section
            with open(self.report_path, "a") as f:
                if not current_content.endswith("\n\n"):
                    f.write("\n")
                f.write(section_text + "\n")

    def wrap_long_text(self, text: str, summary: str = "View details", max_lines: int = 20) -> str:
        """Helper to wrap long text in a collapsible block if it exceeds max_lines."""
        if not text:
            return ""
        lines = text.splitlines()
        if len(lines) > max_lines:
            return f"<details>\n<summary>{summary} ({len(lines)} lines)</summary>\n\n```text\n{text}\n```\n\n</details>"
        return f"```text\n{text}\n```"

    def finalize(self):
        # Optional: add a footer or final summary
        with open(self.report_path, "a") as f:
            f.write("---\n*End of Unified Master Audit Report.*\n")

# Singleton instance for easy access
default_report = MasterReport()
