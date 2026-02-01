"""
Unit tests for Project Homeostasis - Transaction Isolation and Conflict Detection.

Tests cover:
- TransactionShield for Git branch isolation
- ConflictDetector for semantic conflict detection
- Homeostasis integration layer
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from omni.agent.core.cortex.transaction import (
    TransactionShield,
    Transaction,
    TransactionStatus,
    ConflictDetector,
    ConflictReport,
    ConflictSeverity,
)
from omni.agent.core.cortex.homeostasis import (
    Homeostasis,
    HomeostasisConfig,
    HomeostasisResult,
)
from omni.agent.core.cortex.nodes import (
    TaskGraph,
    TaskNode,
    TaskPriority,
)


class TestTransaction:
    """Tests for Transaction dataclass."""

    def test_transaction_creation(self):
        """Test Transaction creation with default values."""
        transaction = Transaction(
            task_id="test_task",
            branch_name="omni-task/test_task",
        )

        assert transaction.task_id == "test_task"
        assert transaction.branch_name == "omni-task/test_task"
        assert transaction.status == TransactionStatus.IDLE
        assert transaction.base_commit == ""
        assert transaction.changes == {}
        assert transaction.conflicts == []

    def test_transaction_hash_and_equality(self):
        """Test Transaction hash and equality."""
        t1 = Transaction(task_id="task_123", branch_name="omni-task/task_123")
        t2 = Transaction(task_id="task_123", branch_name="omni-task/different")
        t3 = Transaction(task_id="task_456", branch_name="omni-task/task_456")

        assert hash(t1) == hash(t2)  # Same task_id
        assert t1 == t2  # Same task_id
        assert t1 != t3  # Different task_id


class TestConflictReport:
    """Tests for ConflictReport dataclass."""

    def test_conflict_report_creation(self):
        """Test ConflictReport creation."""
        report = ConflictReport(
            has_conflicts=True,
            severity=ConflictSeverity.HIGH,
            conflicts=[{"type": "function_signature", "symbol": "connect"}],
            suggestions=["Update call sites"],
            auto_resolvable=False,
        )

        assert report.has_conflicts is True
        assert report.severity == ConflictSeverity.HIGH
        assert len(report.conflicts) == 1
        assert len(report.suggestions) == 1
        assert report.auto_resolvable is False


class TestTransactionShield:
    """Tests for TransactionShield."""

    @pytest.fixture
    def shield(self):
        """Create a TransactionShield instance with mocked repo."""
        shield = TransactionShield(base_branch="main")
        shield._repo_root = Path("/tmp/gitdir")  # Use existing test repo
        return shield

    def test_get_branch_name(self, shield):
        """Test branch name generation."""
        # Short task_id (no truncation)
        branch_name = shield._get_branch_name("test")
        assert branch_name == "omni-task/test"

        # Long task_id (use last 8 chars for uniqueness)
        # "task_update_config" = 18 chars, last 8 = "e_config"
        long_name = "task_update_config"
        branch_name = shield._get_branch_name(long_name)
        assert branch_name == "omni-task/e_config"  # Last 8 chars

        # Task name with meaningful suffix
        # "task_refactor_auth" = 18 chars, last 8 = "tor_auth"
        branch_name = shield._get_branch_name("task_refactor_auth")
        assert branch_name == "omni-task/tor_auth"  # Last 8 chars

        # Exactly 8 chars
        eight_char = "abcdefgh"
        branch_name = shield._get_branch_name(eight_char)
        assert branch_name == "omni-task/abcdefgh"

    @pytest.mark.asyncio
    async def test_get_transaction(self, shield):
        """Test getting a transaction by ID."""
        shield._transactions["task_1"] = Transaction(
            task_id="task_1",
            branch_name="omni-task/task_1",
        )

        transaction = shield.get_transaction("task_1")
        assert transaction is not None
        assert transaction.task_id == "task_1"

        # Non-existent transaction
        assert shield.get_transaction("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_all_transactions(self, shield):
        """Test getting all transactions."""
        shield._transactions = {
            "task_1": Transaction(task_id="task_1", branch_name="branch_1"),
            "task_2": Transaction(task_id="task_2", branch_name="branch_2"),
        }

        all_tx = shield.get_all_transactions()
        assert len(all_tx) == 2
        assert "task_1" in all_tx
        assert "task_2" in all_tx


class TestConflictDetector:
    """Tests for ConflictDetector."""

    @pytest.fixture
    def detector(self):
        """Create a ConflictDetector instance."""
        return ConflictDetector()

    def test_record_symbols(self, detector):
        """Test recording symbols from a branch."""
        symbols = {
            "functions": {"func_a": {"signature": "def func_a(): pass"}},
            "classes": {},
            "imports": [],
        }

        detector.record_symbols("branch_a", symbols)

        assert "branch_a" in detector._previous_symbols
        assert (
            detector._previous_symbols["branch_a"]["functions"]["func_a"]["signature"]
            == "def func_a(): pass"
        )

    def test_detect_conflicts_no_common_symbols(self, detector):
        """Test conflict detection with no common symbols."""
        detector.record_symbols(
            "branch_a",
            {
                "functions": {"func_a": {"signature": "def func_a(): pass"}},
                "classes": {},
                "imports": [],
            },
        )
        detector.record_symbols(
            "branch_b",
            {
                "functions": {"func_b": {"signature": "def func_b(): pass"}},
                "classes": {},
                "imports": [],
            },
        )

        report = detector.detect_conflicts("branch_a", "branch_b")

        assert report.has_conflicts is False
        assert report.severity == ConflictSeverity.NONE
        assert report.auto_resolvable is True

    def test_detect_conflicts_same_function(self, detector):
        """Test no conflict when functions have same signature."""
        detector.record_symbols(
            "branch_a",
            {
                "functions": {
                    "connect": {
                        "signature": "def connect(host: str) -> bool",
                        "return_type": "bool",
                    }
                },
                "classes": {},
                "imports": [],
            },
        )
        detector.record_symbols(
            "branch_b",
            {
                "functions": {
                    "connect": {
                        "signature": "def connect(host: str) -> bool",
                        "return_type": "bool",
                    }
                },
                "classes": {},
                "imports": [],
            },
        )

        report = detector.detect_conflicts("branch_a", "branch_b")

        assert report.has_conflicts is False
        assert report.severity == ConflictSeverity.NONE

    def test_detect_conflicts_function_signature_change(self, detector):
        """Test detecting function signature changes."""
        detector.record_symbols(
            "branch_a",
            {
                "functions": {
                    "connect": {
                        "signature": "def connect(host: str) -> bool",
                        "return_type": "bool",
                    }
                },
                "classes": {},
                "imports": [],
            },
        )
        detector.record_symbols(
            "branch_b",
            {
                "functions": {
                    "connect": {
                        "signature": "def connect(url: str, timeout: int) -> Connection",
                        "return_type": "Connection",
                    }
                },
                "classes": {},
                "imports": [],
            },
        )

        report = detector.detect_conflicts("branch_a", "branch_b")

        assert report.has_conflicts is True
        assert report.severity == ConflictSeverity.HIGH
        assert len(report.conflicts) == 1
        assert report.conflicts[0]["type"] == "function_signature"
        assert "Update call sites" in report.suggestions[0]

    def test_detect_conflicts_class_attributes_removed(self, detector):
        """Test detecting removed class attributes (CRITICAL severity)."""
        detector.record_symbols(
            "branch_a",
            {
                "functions": {},
                "classes": {
                    "Database": {
                        "attributes": {
                            "connection": {"type": "Connection"},
                            "timeout": {"type": "int"},
                        }
                    }
                },
                "imports": [],
            },
        )
        detector.record_symbols(
            "branch_b",
            {
                "functions": {},
                "classes": {
                    "Database": {
                        "attributes": {
                            "connection": {"type": "Connection"},
                            # timeout removed
                        }
                    }
                },
                "imports": [],
            },
        )

        report = detector.detect_conflicts("branch_a", "branch_b")

        assert report.has_conflicts is True
        assert report.severity == ConflictSeverity.CRITICAL
        assert len(report.conflicts) == 1
        assert report.conflicts[0]["type"] == "class_attributes_removed"

    def test_detect_conflicts_attribute_type_change(self, detector):
        """Test detecting attribute type changes (HIGH severity)."""
        detector.record_symbols(
            "branch_a",
            {
                "functions": {},
                "classes": {
                    "Config": {
                        "attributes": {
                            "timeout": {"type": "int"},
                        }
                    }
                },
                "imports": [],
            },
        )
        detector.record_symbols(
            "branch_b",
            {
                "functions": {},
                "classes": {
                    "Config": {
                        "attributes": {
                            "timeout": {"type": "float"},
                        }
                    }
                },
                "imports": [],
            },
        )

        report = detector.detect_conflicts("branch_a", "branch_b")

        assert report.has_conflicts is True
        assert report.severity == ConflictSeverity.HIGH
        assert report.conflicts[0]["type"] == "attribute_type_changed"


class TestHomeostasisConfig:
    """Tests for HomeostasisConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = HomeostasisConfig()

        assert config.enable_isolation is True
        assert config.enable_conflict_detection is True
        assert config.auto_merge_on_success is True
        assert config.auto_rollback_on_failure is True
        assert config.base_branch == "main"
        assert config.verification_timeout == 300
        assert config.max_retries == 2

    def test_custom_config(self):
        """Test custom configuration."""
        config = HomeostasisConfig(
            enable_isolation=False,
            enable_conflict_detection=False,
            auto_merge_on_success=False,
            base_branch="develop",
            max_retries=5,
        )

        assert config.enable_isolation is False
        assert config.enable_conflict_detection is False
        assert config.auto_merge_on_success is False
        assert config.base_branch == "develop"
        assert config.max_retries == 5


class TestHomeostasisResult:
    """Tests for HomeostasisResult."""

    def test_default_result(self):
        """Test default result values."""
        result = HomeostasisResult()

        assert result.success is False
        assert result.total_transactions == 0
        assert result.successful_transactions == 0
        assert result.failed_transactions == 0
        assert result.merged_transactions == 0
        assert result.conflicts_detected == 0
        assert result.duration_ms == 0
        assert result.transactions == {}
        assert result.errors == []

    def test_result_with_data(self):
        """Test result with data."""
        result = HomeostasisResult(
            success=True,
            total_transactions=3,
            successful_transactions=2,
            failed_transactions=1,
            merged_transactions=2,
            conflicts_detected=1,
            duration_ms=1500.0,
            transactions={
                "task_1": {"status": "success"},
                "task_2": {"status": "failed"},
            },
            errors=["Task 2 failed"],
        )

        assert result.success is True
        assert result.total_transactions == 3
        assert result.successful_transactions == 2
        assert result.failed_transactions == 1
        assert result.merged_transactions == 2
        assert result.conflicts_detected == 1
        assert len(result.transactions) == 2
        assert len(result.errors) == 1


class TestHomeostasis:
    """Tests for Homeostasis integration layer."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return HomeostasisConfig(
            enable_isolation=False,  # Disable actual Git for tests
            enable_conflict_detection=True,
            auto_merge_on_success=False,
            auto_rollback_on_failure=True,
        )

    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock orchestrator."""
        orchestrator = MagicMock()
        orchestrator._run_with_solver = AsyncMock(return_value={"output": "success"})
        return orchestrator

    @pytest.fixture
    def homeostasis(self, config, mock_orchestrator):
        """Create a Homeostasis instance."""
        return Homeostasis(config=config, orchestrator=mock_orchestrator)

    @pytest.fixture
    def simple_task_graph(self):
        """Create a simple task graph for testing."""
        graph = TaskGraph(name="test_graph")

        task1 = TaskNode(
            id="task_1",
            description="Test task 1",
            command="echo 'task_1'",
            priority=TaskPriority.HIGH,
            metadata={"file": "file1.py"},
        )

        task2 = TaskNode(
            id="task_2",
            description="Test task 2",
            command="echo 'task_2'",
            priority=TaskPriority.MEDIUM,
            metadata={"file": "file2.py"},
        )

        graph.add_task(task1)
        graph.add_task(task2)

        return graph

    @pytest.mark.asyncio
    async def test_execute_with_protection_success(
        self, homeostasis, simple_task_graph, mock_orchestrator
    ):
        """Test successful execution with protection."""
        result = await homeostasis.execute_with_protection(simple_task_graph)

        assert result.success is True
        assert result.successful_transactions == 2
        assert mock_orchestrator._run_with_solver.call_count == 2

    @pytest.mark.asyncio
    async def test_detect_level_conflicts_no_conflicts(self, homeostasis):
        """Test conflict detection with no conflicts."""
        graph = TaskGraph(name="conflict_test")

        task1 = TaskNode(
            id="task_a",
            description="Task A",
            command="echo 'a'",
            priority=TaskPriority.HIGH,
            metadata={"file": "file_a.py"},
        )

        task2 = TaskNode(
            id="task_b",
            description="Task B",
            command="echo 'b'",
            priority=TaskPriority.HIGH,
            metadata={"file": "file_b.py"},
        )

        graph.add_task(task1)
        graph.add_task(task2)

        report = await homeostasis._detect_level_conflicts(["task_a", "task_b"], graph)

        assert report.has_conflicts is False
        assert report.severity == ConflictSeverity.NONE

    @pytest.mark.asyncio
    async def test_detect_level_conflicts_file_conflict(self, homeostasis):
        """Test conflict detection when both tasks modify same file."""
        graph = TaskGraph(name="file_conflict_test")

        task1 = TaskNode(
            id="task_a",
            description="Task A",
            command="echo 'a'",
            priority=TaskPriority.HIGH,
            metadata={"file": "shared.py"},
        )

        task2 = TaskNode(
            id="task_b",
            description="Task B",
            command="echo 'b'",
            priority=TaskPriority.HIGH,
            metadata={"file": "shared.py"},
        )

        graph.add_task(task1)
        graph.add_task(task2)

        report = await homeostasis._detect_level_conflicts(["task_a", "task_b"], graph)

        assert report.has_conflicts is True
        assert report.severity == ConflictSeverity.MEDIUM
        assert len(report.conflicts) == 1
        assert report.conflicts[0]["type"] == "file_conflict"


class TestIntegrationScenarios:
    """Integration tests for Homeostasis workflow."""

    @pytest.mark.asyncio
    async def test_conflict_detection_chain(self):
        """Test detecting conflicts in a chain of multiple branches."""
        detector = ConflictDetector()

        # Record symbols from multiple branches with same signatures
        detector.record_symbols(
            "branch_1",
            {
                "functions": {"helper": {"signature": "def helper(): pass"}},
                "classes": {"Service": {"attributes": {"name": {"type": "str"}}}},
                "imports": [],
            },
        )

        detector.record_symbols(
            "branch_2",
            {
                "functions": {
                    "helper": {"signature": "def helper(x: int): pass"}
                },  # Different signature
                "classes": {
                    "Service": {"attributes": {"name": {"type": "str"}, "version": {"type": "int"}}}
                },
                "imports": [],
            },
        )

        detector.record_symbols(
            "branch_3",
            {
                "functions": {"helper": {"signature": "def helper(): pass"}},  # Same as branch_1
                "classes": {"Service": {"attributes": {"name": {"type": "str"}}}},
                "imports": [],
            },
        )

        # Check conflicts between branches
        report_1_2 = detector.detect_conflicts("branch_1", "branch_2")
        assert report_1_2.has_conflicts is True
        assert report_1_2.severity == ConflictSeverity.HIGH

        report_1_3 = detector.detect_conflicts("branch_1", "branch_3")
        assert report_1_3.has_conflicts is False
        assert report_1_3.severity == ConflictSeverity.NONE


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "asyncio: mark test as async")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
