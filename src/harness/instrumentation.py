import os
import json
import datetime
from typing import Any, Dict, Optional


class HarnessEventLogger:
    """
    Logger for harness events during sandbox execution.
    Writes JSON lines to a file specified by HARNESS_INSTRUMENTATION_FILE.
    """

    def __init__(self):
        self.log_file = os.environ.get("HARNESS_INSTRUMENTATION_FILE")

    def log_event(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log an event to the instrumentation file.
        
        Args:
            event_type: The type of event (e.g., 'HOOK_START', 'TOOL_USE')
            data: Optional dictionary of event data
        """
        if not self.log_file:
            return

        event = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event_type": event_type,
            "data": data or {}
        }

        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(event) + '\n')
        except Exception:
            # Silent failure to avoid crashing the hook
            pass
