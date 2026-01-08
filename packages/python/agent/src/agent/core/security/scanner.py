"""
agent/core/security/scanner.py
Phase 28: Security Scanner for skill code analysis.

Detects dangerous code patterns using regex and AST analysis.
"""

import re
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SecurityFinding:
    """A single security finding."""

    pattern: str
    severity: str  # "critical", "high", "medium", "low"
    line_number: int
    line_content: str
    description: str
    score: int


@dataclass
class SecurityReport:
    """Security scan report for a skill."""

    skill_path: Path
    skill_name: str
    findings: list[SecurityFinding] = field(default_factory=list)
    total_score: int = 0
    is_blocked: bool = False
    is_warning: bool = False
    scan_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "skill_name": self.skill_name,
            "skill_path": str(self.skill_path),
            "findings": [
                {
                    "pattern": f.pattern,
                    "severity": f.severity,
                    "line_number": f.line_number,
                    "description": f.description,
                    "score": f.score,
                }
                for f in self.findings
            ],
            "total_score": self.total_score,
            "is_blocked": self.is_blocked,
            "is_warning": self.is_warning,
        }


# =============================================================================
# Pattern Definitions
# =============================================================================

# Critical patterns (+50 points)
CRITICAL_PATTERNS = [
    (
        r"os\.system\s*\(",
        "Shell command execution via os.system()",
        50,
    ),
    (
        r"subprocess\.Popen\s*\([^)]*shell\s*=\s*True",
        "Shell injection via subprocess with shell=True",
        50,
    ),
    (
        r"\beval\s*\(",
        "Dynamic code execution via eval()",
        50,
    ),
    (
        r"\bexec\s*\(",
        "Dynamic code execution via exec()",
        50,
    ),
    (
        r"__import__\s*\(",
        "Dynamic module import via __import__()",
        50,
    ),
]

# High patterns (+30 points)
HIGH_PATTERNS = [
    (
        r"open\s*\([^)]*['\"]w['\"]",
        "File write operation",
        30,
    ),
    (
        r"Path\s*\(.*\)\s*\.\s*write_",
        "Path write operation",
        30,
    ),
    (
        r"requests?\s*\.(post|get)\s*\([^)]*timeout\s*=\s*None",
        "Network request without timeout",
        30,
    ),
    (
        r"urllib\d*\.request\s*\(",
        "URL request operation",
        30,
    ),
    (
        r"httpx\s*\.(post|get|Client)",
        "HTTP request operation",
        30,
    ),
    (
        r"socket\.connect\s*\(",
        "Socket connection",
        30,
    ),
]

# Medium patterns (+10 points)
MEDIUM_PATTERNS = [
    (
        r"open\s*\([^)]*['\"]r['\"]",
        "File read operation",
        10,
    ),
    (
        r"Path\s*\(.*\)\s*\.\s*read_",
        "Path read operation",
        10,
    ),
    (
        r"subprocess\.(run|call|Popen)\s*\(",
        "Subprocess execution",
        10,
    ),
    (
        r"subprocess\.(run|call|Popen)\s*\([^)]*shell\s*=\s*False",
        "Subprocess with shell=False (still risky)",
        10,
    ),
    (
        r"os\.popen\s*\(",
        "Shell command via os.popen",
        10,
    ),
    (
        r"os\.chmod\s*\(",
        "File permission change",
        10,
    ),
    (
        r"os\.chown\s*\(",
        "File ownership change",
        10,
    ),
]

# Low patterns (+5 points)
LOW_PATTERNS = [
    (
        r"os\.getcwd\s*\(",
        "Get current working directory",
        5,
    ),
    (
        r"os\.listdir\s*\(",
        "List directory contents",
        5,
    ),
    (
        r"os\.path\.",
        "OS path operations",
        5,
    ),
    (
        r"pathlib\.",
        "Path operations",
        5,
    ),
    (
        r"sys\.(path|argv|executable)",
        "System access",
        5,
    ),
    (
        r"getattr\s*\(",
        "Get attribute (potential reflection)",
        5,
    ),
    (
        r"setattr\s*\(",
        "Set attribute (potential reflection)",
        5,
    ),
]

# Path traversal patterns (+20 points)
PATH_TRAVERSAL_PATTERNS = [
    (
        r"\.\./",
        "Path traversal attempt (../)",
        20,
    ),
    (
        r"\.\.\\",
        "Path traversal attempt (..\\)",
        20,
    ),
    (
        r"%2e%2e",
        "URL-encoded path traversal",
        20,
    ),
]


# =============================================================================
# AST Analysis
# =============================================================================


class DangerousCallVisitor(ast.NodeVisitor):
    """AST visitor to detect dangerous function calls."""

    def __init__(self):
        self.findings: list[SecurityFinding] = []
        self.current_line = 1

    def visit_Call(self, node: ast.Call):
        """Visit function call nodes."""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        else:
            func_name = str(node.func)

        # Check for dangerous patterns in calls
        dangerous_calls = {
            "system": ("os.system() call", 50),
            "popen": ("os.popen() call", 10),
            "chmod": ("os.chmod() call", 10),
            "chown": ("os.chown() call", 10),
            "getcwd": ("os.getcwd() call", 5),
            "listdir": ("os.listdir() call", 5),
            "exec": ("exec() call", 50),
            "eval": ("eval() call", 50),
        }

        if func_name in dangerous_calls:
            desc, score = dangerous_calls[func_name]
            self.findings.append(
                SecurityFinding(
                    pattern=func_name,
                    severity="high" if score >= 30 else "medium" if score >= 10 else "low",
                    line_number=node.lineno,
                    line_content=ast.get_source_segment(self.source_code, node)
                    or f"{func_name}(...)",
                    description=desc,
                    score=score,
                )
            )

        self.generic_visit(node)


# =============================================================================
# Security Scanner
# =============================================================================


class SecurityScanner:
    """
    Scan skill code for security issues.

    Usage:
        scanner = SecurityScanner()
        report = scanner.scan(Path("/path/to/skill"))
        print(f"Score: {report.total_score}, Blocked: {report.is_blocked}")
    """

    def __init__(self):
        self.compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> dict:
        """Compile regex patterns for efficient scanning."""
        return {
            "critical": [(re.compile(p, re.IGNORECASE), d, s) for p, d, s in CRITICAL_PATTERNS],
            "high": [(re.compile(p, re.IGNORECASE), d, s) for p, d, s in HIGH_PATTERNS],
            "medium": [(re.compile(p, re.IGNORECASE), d, s) for p, d, s in MEDIUM_PATTERNS],
            "low": [(re.compile(p, re.IGNORECASE), d, s) for p, d, s in LOW_PATTERNS],
            "path_traversal": [
                (re.compile(p, re.IGNORECASE), d, s) for p, d, s in PATH_TRAVERSAL_PATTERNS
            ],
        }

    def scan(self, skill_path: Path) -> SecurityReport:
        """
        Scan a skill directory for security issues.

        Args:
            skill_path: Path to the skill directory

        Returns:
            SecurityReport with findings and score
        """
        skill_name = skill_path.name
        report = SecurityReport(skill_path=skill_path, skill_name=skill_name)

        # Find all Python files
        py_files = list(skill_path.rglob("*.py"))

        if not py_files:
            # No Python files to scan
            return report

        for py_file in py_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                relative_path = py_file.relative_to(skill_path)
                file_findings = self._scan_file(content, str(relative_path))
                report.findings.extend(file_findings)
            except Exception as e:
                report.scan_errors.append(f"Error scanning {py_file}: {str(e)}")

        # Calculate total score
        report.total_score = sum(f.score for f in report.findings)

        # Determine block/warn status (configurable thresholds)
        from common.config.settings import get_setting

        block_threshold = get_setting("security.block_threshold", 30)
        warn_threshold = get_setting("security.warn_threshold", 10)

        report.is_blocked = report.total_score >= block_threshold
        report.is_warning = report.total_score >= warn_threshold

        return report

    def _scan_file(self, content: str, file_path: str) -> list[SecurityFinding]:
        """Scan a single file for security issues."""
        findings = []
        lines = content.split("\n")

        for severity, patterns in self.compiled_patterns.items():
            for pattern, desc, score in patterns:
                for match in pattern.finditer(content):
                    line_no = content[: match.start()].count("\n") + 1
                    line_content = lines[line_no - 1] if line_no <= len(lines) else ""

                    # Findings only for code patterns (not string literals)
                    if not self._is_in_string_literal(content, match.start()):
                        findings.append(
                            SecurityFinding(
                                pattern=pattern.pattern,
                                severity=severity,
                                line_number=line_no,
                                line_content=line_content.strip()[:100],
                                description=desc,
                                score=score,
                            )
                        )

        # Run AST analysis
        try:
            tree = ast.parse(content)
            visitor = DangerousCallVisitor()
            visitor.source_code = content
            visitor.visit(tree)
            findings.extend(visitor.findings)
        except SyntaxError:
            # Skip AST analysis for files with syntax errors
            pass

        return findings

    def _is_in_string_literal(self, content: str, position: int) -> bool:
        """Check if a position is inside a string literal."""
        # Simple heuristic: count quotes before position
        before = content[:position]
        # Count quotes that would open a string
        in_string = False
        i = 0
        while i < len(before):
            if before[i] == "\\":
                i += 2
                continue
            if before[i] in ('"', "'"):
                if not in_string:
                    in_string = True
                    quote_char = before[i]
                elif before[i] == quote_char:
                    in_string = False
            i += 1
        return in_string

    def scan_code(self, code: str, skill_name: str = "unknown") -> SecurityReport:
        """
        Scan a code string directly.

        Args:
            code: Python code to scan
            skill_name: Name of the skill

        Returns:
            SecurityReport with findings and score
        """
        report = SecurityReport(
            skill_path=Path("."),
            skill_name=skill_name,
        )

        findings = self._scan_file(code, "<inline>")
        report.findings = findings
        report.total_score = sum(f.score for f in findings)

        from common.config.settings import get_setting

        block_threshold = get_setting("security.block_threshold", 30)
        warn_threshold = get_setting("security.warn_threshold", 10)

        report.is_blocked = report.total_score >= block_threshold
        report.is_warning = report.total_score >= warn_threshold

        return report

    def check_dependencies(self, manifest: dict, skill_path: Path) -> list[str]:
        """
        Check for vulnerable dependencies.

        Args:
            manifest: Skill manifest dict
            skill_path: Path to skill directory

        Returns:
            List of warnings about dependencies
        """
        warnings = []

        # Check requirements.txt or pyproject.toml
        req_files = ["requirements.txt", "pyproject.toml", "Pipfile"]
        for req_file in req_files:
            req_path = skill_path / req_file
            if req_path.exists():
                content = req_path.read_text()
                # Check for known vulnerable packages (simplified)
                # In production, would use safety or pyup API
                dangerous_packages = ["requests", "urllib3"]
                for pkg in dangerous_packages:
                    if re.search(rf"{pkg}\s*[<>=!~]", content, re.IGNORECASE):
                        version_match = re.search(
                            rf"{pkg}\s*([<>=!~]+[\d.]+)", content, re.IGNORECASE
                        )
                        version = version_match.group(1) if version_match else ""
                        warnings.append(f"{pkg} {version} - verify version is up to date")

        return warnings
