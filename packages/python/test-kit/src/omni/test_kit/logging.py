import logging
import sys
from typing import Optional


def setup_test_logging(level: int = logging.DEBUG):
    """Setup structured logging for tests to assist in tracing."""
    # Configure root logger for tests
    logging.basicConfig(
        level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stdout
    )

    # Silence noisy loggers
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)


class TestTracer:
    """Utility to trace execution steps in complex workflows."""

    def __init__(self, name: str):
        self.name = name
        self.steps = []
        self.logger = logging.getLogger(f"omni.test.trace.{name}")

    def log_step(self, step_name: str, data: Optional[dict] = None):
        """Record a workflow step."""
        self.steps.append({"step": step_name, "data": data})
        self.logger.debug(f"STEP: {step_name} | DATA: {data}")

    def assert_step_occurred(self, step_name: str):
        """Verify that a specific step was reached."""
        assert any(s["step"] == step_name for s in self.steps), (
            f"Step {step_name} never occurred in trace {self.name}"
        )
