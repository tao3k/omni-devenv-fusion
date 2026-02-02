"""
omega.py - Project Omega: The Unified Hub

Omni-Dev-Fusion 的最高等级执行器。
统筹 Cortex (调度), Homeostasis (隔离), Cerebellum (导航) 与 Hippocampus (记忆)。

Features:
- Semantic pre-check via Cerebellum (AST analysis)
- Experience loading via Hippocampus (memory recall)
- Task decomposition via Cortex (parallel DAG)
- Isolated execution via Homeostasis + OmniCell
- Conflict resolution via Immune System
- Skill crystallization via Evolution

Event System:
- Uses omni-events topics (omega/mission/start, omega/task/start, etc.)
- Events forwarded to TUI via TUIBridge Unix socket
- See: packages/rust/crates/omni-events/src/lib.rs
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from omni.foundation.config.logging import get_logger

from omni.agent.core.cortex.nodes import TaskGraph, TaskNode, TaskPriority
from omni.agent.core.cortex import (
    TaskDecomposer,
    CortexOrchestrator,
    Homeostasis,
    HomeostasisConfig,
    ConflictDetector,
)

logger = get_logger("omni.omega")

# Omega event topic constants (matching omni-events rust crate)
OMEGA_TOPICS = {
    "MISSION_START": "omega/mission/start",
    "MISSION_COMPLETE": "omega/mission/complete",
    "MISSION_FAIL": "omega/mission/fail",
    "SEMANTIC_SCAN": "omega/semantic/scan",
    "SEMANTIC_COMPLETE": "omega/semantic/complete",
    "EXPERIENCE_LOAD": "omega/experience/load",
    "EXPERIENCE_LOADED": "omega/experience/loaded",
    "TASK_DECOMPOSE": "omega/task/decompose",
    "TASK_DECOMPOSED": "omega/task/decomposed",
    "BRANCH_ISOLATE": "omega/branch/isolate",
    "BRANCH_CREATED": "omega/branch/created",
    "BRANCH_MERGED": "omega/branch/merged",
    "BRANCH_ROLLBACK": "omega/branch/rollback",
    "TASK_START": "omega/task/start",
    "TASK_COMPLETE": "omega/task/complete",
    "TASK_FAIL": "omega/task/fail",
    "CONFLICT_DETECTED": "omega/conflict/detected",
    "CONFLICT_RESOLVED": "omega/conflict/resolved",
    "RECOVERY_TRIGGER": "omega/recovery/trigger",
    "RECOVERY_SUCCESS": "omega/recovery/success",
    "SKILL_CRYSTALLIZE": "omega/skill/crystallize",
    "SKILL_CRYSTALLIZED": "omega/skill/crystallized",
}


@dataclass
class MissionConfig:
    """Configuration for an Omega mission."""

    goal: str
    enable_isolation: bool = True
    enable_conflict_detection: bool = True
    enable_memory_recall: bool = True
    enable_skill_crystallization: bool = True
    auto_merge: bool = True
    auto_recovery: bool = True
    max_retries: int = 2
    parallel_workers: int = 4


@dataclass
class MissionResult:
    """Result of an Omega mission."""

    success: bool
    goal: str
    duration_ms: float
    tasks_total: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    recovery_attempts: int = 0
    branches_created: int = 0
    skill_crystallized: int = 0
    events: list[dict] = field(default_factory=list)  # List of omni-events format dicts
    errors: list[str] = field(default_factory=list)


class OmegaDashboard:
    """Rich-based dashboard for Omega execution."""

    # Event type to icon mapping
    EVENT_ICONS = {
        "MISSION_START": "🚀",
        "MISSION_COMPLETE": "🎉",
        "MISSION_FAIL": "💥",
        "SEMANTIC_SCAN": "🔍",
        "SEMANTIC_COMPLETE": "✅",
        "EXPERIENCE_LOAD": "🧠",
        "EXPERIENCE_LOADED": "💡",
        "TASK_DECOMPOSE": "📋",
        "TASK_DECOMPOSED": "📋",
        "BRANCH_ISOLATE": "🌿",
        "BRANCH_CREATED": "🌱",
        "BRANCH_MERGED": "🔀",
        "BRANCH_ROLLBACK": "⏪",
        "TASK_START": "⚙️",
        "TASK_COMPLETE": "✅",
        "TASK_FAIL": "❌",
        "CONFLICT_DETECTED": "⚠️",
        "CONFLICT_RESOLVED": "🔧",
        "RECOVERY_TRIGGER": "🔄",
        "RECOVERY_SUCCESS": "🔁",
        "SKILL_CRYSTALLIZE": "💎",
        "SKILL_CRYSTALLIZED": "✨",
    }

    # Event type to style mapping
    EVENT_STYLES = {
        "TASK_FAIL": "red",
        "CONFLICT_DETECTED": "yellow",
        "RECOVERY_TRIGGER": "magenta",
        "RECOVERY_SUCCESS": "cyan",
        "MISSION_COMPLETE": "green",
        "MISSION_FAIL": "red",
        "CONFLICT_RESOLVED": "green",
    }

    def __init__(self):
        from rich.console import Console
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        from rich.panel import Panel
        from rich.layout import Layout
        from rich.text import Text

        self.console = Console()
        self.layout = Layout()
        self.layout.split_column(
            Layout(
                Panel(Text("Ω MEGA", style="bold magenta"), height=3, border_style="cyan"),
                name="header",
            ),
            Layout(name="main"),
        )
        self.layout["main"].split_row(
            Layout(name="threads"),
            Layout(name="events"),
        )

        # Progress bars for threads
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            expand=False,
        )

        self.thread_tasks: dict[str, int] = {}

    def start_mission(self, goal: str):
        """Start mission display."""
        from rich.panel import Panel
        from rich.text import Text

        self.console.print(
            Panel(
                f"[bold yellow]🚀 Mission:[/bold yellow] {goal}",
                title="Ω MEGA",
                border_style="cyan",
            )
        )

    def create_thread(self, thread_id: str, description: str):
        """Create a new thread progress bar."""
        self.thread_tasks[thread_id] = self.progress.add_task(description, total=100)

    def update_thread(self, thread_id: str, advance: float = 1, message: str = ""):
        """Update thread progress."""
        if thread_id in self.thread_tasks:
            self.progress.advance(self.thread_tasks[thread_id], advance)
            if message:
                self.progress.update(self.thread_tasks[thread_id], description=message)

    def complete_thread(self, thread_id: str, success: bool = True):
        """Complete a thread."""
        if thread_id in self.thread_tasks:
            self.progress.update(self.thread_tasks[thread_id], completed=100, visible=False)
            del self.thread_tasks[thread_id]

    def log_event(self, event: dict):
        """Log an event (omni-events format dict)."""
        topic = event.get("topic", "")
        message = event.get("message", "")
        timestamp = event.get("timestamp", "")

        # Extract event type from topic (e.g., "omega/mission/start" -> "MISSION_START")
        event_type = topic.split("/")[-1].upper() if topic else ""
        event_type = event_type.replace("-", "_")

        icon = self.EVENT_ICONS.get(event_type, "•")
        style = self.EVENT_STYLES.get(event_type, "white")

        self.console.print(f"[{style}]{icon}[/] {timestamp} {message}")

    async def run_with_dashboard(self, coro, goal: str):
        """Run coroutine with dashboard display."""
        import threading

        self.start_mission(goal)

        # Run progress in a separate thread
        progress_thread = threading.Thread(
            target=self.progress.console.print, args=(self.progress,), daemon=True
        )
        progress_thread.start()

        # Start progress
        self.progress.start()

        try:
            result = await coro
            self.progress.stop()
            return result
        except Exception as e:
            self.progress.stop()
            raise


class RecoveryNode:
    """Self-healing recovery node for failed tasks."""

    def __init__(self, hippocampus=None, conflict_detector=None):
        self.hippocampus = hippocampus
        self.conflict_detector = conflict_detector or ConflictDetector()
        self.recovery_strategies: list[dict] = []

    async def attempt_recovery(
        self,
        failed_task: TaskNode,
        error: str,
        context: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Attempt to recover from a failed task.

        Returns:
            (success: bool, message: str)
        """
        logger.info(
            "omega.recovery_triggered",
            task_id=failed_task.id,
            error=error[:200],
        )

        # Step 1: Recall similar failures from memory
        similar_fix = None
        if self.hippocampus:
            try:
                from omni.foundation.services.memory.base import MemoryType

                memories = await self.hippocampus.query(
                    query=f"Error: {error}",
                    memory_type=MemoryType.EXPERIENCE,
                    limit=3,
                )
                if memories:
                    similar_fix = memories[0].get("solution", "")
                    logger.info(
                        "omega.similar_fix_found",
                        fix=similar_fix[:200] if similar_fix else None,
                    )
            except Exception as e:
                logger.warning("omega.memory_recall_failed", error=str(e))

        # Step 2: Generate recovery plan
        recovery_plan = await self._generate_recovery_plan(failed_task, error, similar_fix, context)

        # Step 3: Return recovery plan for execution
        if recovery_plan:
            return True, f"Recovery strategy: {recovery_plan}"
        return False, "No recovery strategy found"

    async def _generate_recovery_plan(
        self,
        failed_task: TaskNode,
        error: str,
        similar_fix: str | None,
        context: dict[str, Any],
    ) -> str:
        """Generate a recovery plan based on error and history."""
        # Common recovery strategies
        strategies = []

        if "SyntaxError" in error or "IndentationError" in error:
            strategies.append("Fix syntax errors in the generated code")
            strategies.append("Run syntax validator before commit")

        if "ImportError" in error or "ModuleNotFoundError" in error:
            strategies.append("Check and install missing dependencies")
            strategies.append("Verify import paths are correct")

        if "Conflict" in error or "merge" in error.lower():
            strategies.append("Resolve merge conflicts manually")
            strategies.append("Rebase on latest main branch")

        if "PermissionError" in error or "Access denied" in error:
            strategies.append("Check file permissions")
            strategies.append("Verify user has write access")

        if similar_fix:
            strategies.append(f"Apply similar fix from history: {similar_fix[:100]}...")

        if strategies:
            return " | ".join(strategies)
        return "Manual intervention required"

    def register_recovery_strategy(self, error_pattern: str, strategy: str):
        """Register a custom recovery strategy."""
        self.recovery_strategies.append(
            {
                "pattern": error_pattern,
                "strategy": strategy,
            }
        )


class OmegaRunner:
    """
    Omni-Dev-Fusion 的最高等级执行器。

    统筹:
    - Cortex (调度): 任务分解和并行执行
    - Homeostasis (隔离): Git 分支隔离和冲突检测
    - Cerebellum (导航): AST 语义扫描
    - Hippocampus (记忆): 经验加载和存储
    - Evolution (进化): 技能结晶

    Usage:
        runner = OmegaRunner()
        result = await runner.run_mission("优化全库性能")

    Event System:
        Events are emitted in omni-events format:
        {
            "source": "omega",
            "topic": "omega/mission/start",
            "payload": {"message": "...", "data": {...}},
            "timestamp": "ISO8601"
        }
    """

    def __init__(
        self,
        config: MissionConfig | None = None,
        cortex_orchestrator: CortexOrchestrator | None = None,
        homeostasis: Homeostasis | None = None,
        hippocampus=None,
        tui_bridge=None,
    ):
        """Initialize OmegaRunner."""
        self.config = config or MissionConfig(goal="default")
        self.cortex = cortex_orchestrator or CortexOrchestrator()
        self.homeostasis = homeostasis or Homeostasis(
            config=HomeostasisConfig(
                enable_isolation=self.config.enable_isolation,
                enable_conflict_detection=self.config.enable_conflict_detection,
                auto_merge_on_success=self.config.auto_merge,
                auto_rollback_on_failure=True,
            )
        )
        self.hippocampus = hippocampus
        self.recovery_node = RecoveryNode(hippocampus=self.hippocampus)
        self.dashboard = OmegaDashboard()
        self.events: list[dict] = []

        # TUI Bridge for real-time updates
        self.tui_bridge = tui_bridge

        # Metrics
        self._start_time: datetime | None = None
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._conflicts_detected = 0
        self._recovery_attempts = 0

    def _emit(self, topic_key: str, message: str, data: dict | None = None):
        """
        Emit an event in omni-events format.

        Args:
            topic_key: Key from OMEGA_TOPICS (e.g., "MISSION_START")
            message: Human-readable message
            data: Additional payload data
        """
        topic = OMEGA_TOPICS.get(topic_key, f"omega/{topic_key.lower()}")
        timestamp = datetime.now().isoformat()

        event = {
            "source": "omega",
            "topic": topic,
            "payload": {
                "message": message,
                "data": data or {},
            },
            "timestamp": timestamp,
        }

        self.events.append(event)
        self.dashboard.log_event(event)

        # Also send to TUI if connected
        if self.tui_bridge and self.tui_bridge.is_connected:
            try:
                self.tui_bridge.send_event(event)
            except Exception:
                pass

    async def run_mission(self, goal: str) -> MissionResult:
        """
        Execute a mission using the full Omega pipeline.

        Pipeline:
        1. Semantic Pre-check (Cerebellum) - 扫描全库，评估复杂度
        2. Experience Load (Hippocampus) - 寻找历史上类似的成功路径
        3. Task Decompose (Cortex) - 生成并行 DAG 任务图
        4. Isolated Execution (Homeostasis + OmniCell) - 每个节点在独立分支运行
        5. Conflict Merge & Audit (Immune) - 检查语义冲突，通过后合并
        6. Skill Crystallize (Evolution) - 成功的逻辑转化为 Skill
        """
        self._start_time = datetime.now()
        self.events.clear()
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._conflicts_detected = 0
        self._recovery_attempts = 0

        self._emit("MISSION_START", f"开始执行任务: {goal}", {"goal": goal})

        try:
            # Step 1: Semantic Pre-check
            self._emit("SEMANTIC_SCAN", "正在进行语义预检...")
            semantic_analysis = await self._semantic_precheck(goal)
            self._emit(
                "SEMANTIC_COMPLETE",
                f"语义分析完成: {semantic_analysis.get('risk_level', 'unknown')} 风险",
                semantic_analysis,
            )

            # Step 2: Experience Load
            if self.config.enable_memory_recall:
                self._emit("EXPERIENCE_LOAD", "正在加载历史经验...")
                experience = await self._load_experience(goal)
                self._emit(
                    "EXPERIENCE_LOADED", f"找到 {experience.get('count', 0)} 条相关经验", experience
                )

            # Step 3: Task Decompose
            self._emit("TASK_DECOMPOSE", "正在分解任务...")
            task_graph = await self._decompose_task(goal, semantic_analysis)
            self._emit(
                "TASK_DECOMPOSED",
                f"任务已分解为 {len(task_graph.all_tasks)} 个子任务",
                {"task_count": len(task_graph.all_tasks)},
            )

            # Step 4: Isolated Execution with Homeostasis
            self._emit("BRANCH_ISOLATE", "开始隔离执行...")
            execution_result = await self._execute_with_protection(task_graph)

            self._tasks_completed = execution_result.successful_transactions
            self._tasks_failed = execution_result.failed_transactions
            self._conflicts_detected = execution_result.conflicts_detected

            # Step 5: Skill Crystallization
            if self.config.enable_skill_crystallization and execution_result.success:
                self._emit("SKILL_CRYSTALLIZE", "正在结晶技能...")
                await self._crystallize_skill(goal, task_graph, execution_result)

            # Complete
            duration_ms = (datetime.now() - self._start_time).total_seconds() * 1000
            self._emit("MISSION_COMPLETE", f"任务完成! 耗时: {duration_ms:.0f}ms")

            return MissionResult(
                success=True,
                goal=goal,
                duration_ms=duration_ms,
                tasks_total=len(task_graph.all_tasks),
                tasks_completed=self._tasks_completed,
                tasks_failed=self._tasks_failed,
                conflicts_detected=self._conflicts_detected,
                conflicts_resolved=execution_result.conflicts_detected,
                recovery_attempts=self._recovery_attempts,
                events=self.events,
            )

        except Exception as e:
            duration_ms = (datetime.now() - self._start_time).total_seconds() * 1000
            logger.error("omega.mission_failed", error=str(e))

            self._emit("MISSION_FAIL", f"任务失败: {str(e)}")

            return MissionResult(
                success=False,
                goal=goal,
                duration_ms=duration_ms,
                tasks_completed=self._tasks_completed,
                tasks_failed=self._tasks_failed,
                errors=[str(e)],
                events=self.events,
            )

    async def _semantic_precheck(self, goal: str) -> dict[str, Any]:
        """Semantic pre-check using Cerebellum/AST analysis."""
        # Simplified: Analyze goal complexity
        complexity_indicators = ["全库", "所有", "批量", "批量修改", "重构"]
        risk_level = "low"

        for indicator in complexity_indicators:
            if indicator in goal:
                risk_level = "high"
                break

        # Check for dangerous operations
        dangerous = ["rm -rf", "delete", "drop", "truncate"]
        for op in dangerous:
            if op.lower() in goal.lower():
                risk_level = "critical"
                break

        return {
            "risk_level": risk_level,
            "estimated_files": 10 if risk_level == "low" else 100,
            "complexity": "high" if risk_level in ["high", "critical"] else "medium",
        }

    async def _load_experience(self, goal: str) -> dict[str, Any]:
        """Load relevant experience from Hippocampus."""
        if not self.hippocampus:
            return {"count": 0, "experiences": []}

        try:
            from omni.foundation.services.memory.base import MemoryType

            memories = await self.hippocampus.query(
                query=goal,
                memory_type=MemoryType.EXPERIENCE,
                limit=5,
            )
            return {
                "count": len(memories),
                "experiences": memories,
            }
        except Exception as e:
            logger.warning("omega.experience_load_failed", error=str(e))
            return {"count": 0, "error": str(e)}

    async def _decompose_task(
        self,
        goal: str,
        semantic_analysis: dict[str, Any],
    ) -> TaskGraph:
        """Decompose goal into parallel task graph."""
        decomposer = TaskDecomposer()
        result = await decomposer.decompose(goal)

        if result.success:
            return result.task_graph

        # Fallback: create a simple single-task graph
        graph = TaskGraph(name="omega_mission")
        task = TaskNode(
            id=f"task_{uuid.uuid4().hex[:8]}",
            description=goal,
            command=goal,  # Will be interpreted by OmniCell
            priority=TaskPriority.HIGH,
            metadata={"original_goal": goal},
        )
        graph.add_task(task)
        return graph

    async def _execute_with_protection(self, task_graph: TaskGraph) -> Any:
        """Execute with Homeostasis protection."""
        return await self.homeostasis.execute_with_protection(task_graph)

    async def _crystallize_skill(
        self,
        goal: str,
        task_graph: TaskGraph,
        result: Any,
    ) -> int:
        """Crystallize successful logic into a skill."""
        # This would integrate with Evolution/UniversalSolver
        # For now, log the intent
        logger.info(
            "omega.skill_crystallize",
            goal=goal,
            tasks=len(task_graph.all_tasks),
        )
        return 1


class CortexDashboard:
    """
    Real-time dashboard for parallel task execution.

    Features:
    - Thread progress bars
    - Branch isolation status
    - Conflict detection alerts
    - System state overview
    """

    def __init__(self):
        from rich.console import Console
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        from rich.live import Live

        self.console = Console()
        self.live = None

        # Progress for each thread
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=None),
            expand=True,
        )
        self.tasks: dict[str, str] = {}  # task_id -> description

        # Thread status table
        self.status_table = Table(title="Thread Status", show_header=True)
        self.status_table.add_column("Thread", style="cyan")
        self.status_table.add_column("Status", style="green")
        self.status_table.add_column("Branch", style="yellow")
        self.status_table.add_column("Progress", style="magenta")

    def start(self, mission: str):
        """Start the dashboard."""
        self.console.print(
            Panel(
                Text(f"🚀 Cortex Dashboard - {mission}", style="bold cyan"),
                border_style="cyan",
            )
        )
        self.live = Live(self.progress, console=self.console, refresh_per_second=4)
        self.live.start()

    def add_thread(self, thread_id: str, description: str, branch: str = None):
        """Add a new thread to monitor."""
        desc = f"[Thread {thread_id}] {description}"
        if branch:
            desc += f" ({branch})"
        self.tasks[thread_id] = self.progress.add_task(desc, total=100)

    def update_thread(self, thread_id: str, advance: float, message: str = None):
        """Update thread progress."""
        if thread_id in self.tasks:
            self.progress.advance(self.tasks[thread_id], advance)
            if message:
                desc = self.progress.tasks[self.tasks[thread_id]].description
                self.progress.update(self.tasks[thread_id], description=message)

    def set_thread_status(self, thread_id: str, status: str):
        """Set thread status."""
        if thread_id in self.tasks:
            self.progress.update(self.tasks[thread_id], description=f"[{status}] {thread_id}")

    def remove_thread(self, thread_id: str):
        """Remove a thread."""
        if thread_id in self.tasks:
            self.progress.update(self.tasks[thread_id], completed=100, visible=False)
            del self.tasks[thread_id]

    def log_conflict(self, task_a: str, task_b: str, file: str):
        """Log a conflict detection."""
        self.console.print(f"[yellow]⚠️  Conflict detected:[/yellow] {task_a} vs {task_b} on {file}")

    def log_event(self, event_type: str, message: str, style: str = "white"):
        """Log an event."""
        self.console.print(f"[{style}][{event_type.upper()}][/] {message}")

    def stop(self, summary: dict = None):
        """Stop the dashboard."""
        if self.live:
            self.live.stop()

        # Print summary
        self.console.print(
            Panel(
                Text("✅ Execution Complete", style="bold green"),
                title="Cortex Dashboard",
                border_style="green",
            )
        )

        if summary:
            from rich.table import Table

            table = Table(show_header=False)
            table.add_row("Tasks", str(summary.get("completed", 0)))
            table.add_row("Failed", str(summary.get("failed", 0)))
            table.add_row("Conflicts", str(summary.get("conflicts", 0)))
            self.console.print(table)


__all__ = [
    "OmegaRunner",
    "OMEGA_TOPICS",  # Event topic constants matching omni-events
    "MissionConfig",
    "MissionResult",
    "RecoveryNode",
    "CortexDashboard",
    "OmegaDashboard",
]
