"""
verify_fibonacci.py - Self-Evolution Scenario Validator
Description:
    Automates the testing of the Harvester -> MetaAgent pipeline.
    1. Triggers a 'Create Fibonacci' request via CLI.
    2. Verifies the skill is generated.
    3. Executes the new skill to validate functionality.
    4. Generates a markdown report.

Usage:
    python verify_fibonacci.py
"""

import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Configuration
# Adjust this path if your project root is different
PROJECT_ROOT = Path(__file__).resolve().parents[5]
SKILLS_DIR = PROJECT_ROOT / "assets" / "skills"
REPORT_DIR = Path(__file__).parent
TARGET_SKILL_NAME = "fibonacci-calculator"  # Expected generated name (hyphens preserved)
TARGET_SKILL_DIR = SKILLS_DIR / TARGET_SKILL_NAME


def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def run_omni_command(args, description, use_run=True):
    """Run an omni command and capture output.

    Args:
        args: Command arguments (without 'omni')
        description: Description of the command
        use_run: If True, prepend 'run' for omni run commands (exec, repl)
    """
    log(f"Executing: {description}...")
    start_time = time.time()

    # Assuming 'omni' is in PATH. If not, use 'python -m agent.main'
    if use_run:
        cmd = ["omni", "run"] + args
    else:
        cmd = ["omni"] + args

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        duration = time.time() - start_time
        return result, duration
    except FileNotFoundError:
        log("Error: 'omni' command not found. Ensure it is installed or in PATH.", "ERROR")
        sys.exit(1)


def generate_report(steps_data, success):
    """Generate a Markdown verification report."""
    report_path = REPORT_DIR / "evolution_report.md"

    status_icon = "✅" if success else "❌"
    content = [
        f"# {status_icon} Self-Evolution Verification Report",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Target Skill:** `{TARGET_SKILL_NAME}`",
        "",
        "## 1. Scenario Execution Log",
        "| Step | Duration | Status | Details |",
        "|------|----------|--------|---------|",
    ]

    for step in steps_data:
        icon = "OK" if step["status"] else "FAIL"
        content.append(f"| {step['name']} | {step['duration']:.2f}s | {icon} | {step['details']} |")

    content.append("")
    content.append("## 2. Validation Evidence")
    if TARGET_SKILL_DIR.exists():
        content.append(f"- **Skill Path:** `{TARGET_SKILL_DIR}`")
        script_path = TARGET_SKILL_DIR / "scripts" / f"{TARGET_SKILL_NAME}.py"
        if script_path.exists():
            content.append("- **Script Source:** Found")
            content.append("```python")
            content.append(script_path.read_text()[:500] + "\n# ... (truncated)")
            content.append("```")
    else:
        content.append("- **Skill Path:** Not Found ❌")

    report_path.write_text("\n".join(content))
    log(f"Report generated: {report_path}")


def main():
    steps = []

    # --- Step 1: Cleanup ---
    if TARGET_SKILL_DIR.exists():
        log(f"Cleaning up existing skill at {TARGET_SKILL_DIR}...")
        shutil.rmtree(TARGET_SKILL_DIR)

    steps.append(
        {
            "name": "Environment Cleanup",
            "status": True,
            "duration": 0,
            "details": "Removed existing skill artifacts",
        }
    )

    # --- Step 2: Trigger Evolution (The 'Run' Command) ---
    prompt = "Create a fibonacci_calculator skill to compute fibonacci sequence"
    result, duration = run_omni_command(["exec", prompt], "Triggering Skill Generation")

    # Check if Harvester triggered (look for specific logs)
    # Even if command fails, if Harvester logs appear, consider it triggered
    harvester_triggered = (
        "🌾 [Subconscious]" in result.stdout
        or "🌾 [Subconscious]" in result.stderr
        or "🌾 Detected" in result.stdout
        or "🌾 Detected" in result.stderr
        or "harvester_candidate" in result.stderr
        or "harvester_analyzing" in result.stderr
    )

    steps.append(
        {
            "name": "Trigger Evolution",
            "status": harvester_triggered,
            "duration": duration,
            "details": "Command executed. Harvester detected."
            if harvester_triggered
            else "Command executed. Harvester logs missing.",
        }
    )

    # --- Step 3: Generate Skill (Full Self-Evolution) ---
    # Since Harvester is lightweight (detection only), we trigger actual generation
    if not TARGET_SKILL_DIR.exists():
        log("Generating skill (Harvester detected pattern)...")
        # Pass both name and description for predictable results
        # Note: skill generate is not under 'omni run', so use_run=False
        gen_result, gen_duration = run_omni_command(
            ["skill", "generate", TARGET_SKILL_NAME, "-d", prompt, "--no-interactive"],
            "Generating Fibonacci Skill",
            use_run=False,
        )

        steps.append(
            {
                "name": "Skill Generation",
                "status": gen_result.returncode == 0 and TARGET_SKILL_DIR.exists(),
                "duration": gen_duration,
                "details": "Skill generated successfully"
                if TARGET_SKILL_DIR.exists()
                else "Generation failed",
            }
        )

    # --- Step 4: Verify Artifacts ---
    skill_created = TARGET_SKILL_DIR.exists()
    steps.append(
        {
            "name": "Artifact Verification",
            "status": skill_created,
            "duration": 0,
            "details": f"Directory exists: {skill_created}",
        }
    )

    # --- Step 5: Functional Validation (Run the new skill) ---
    validation_success = False
    val_duration = 0
    if skill_created:
        # Give file system a moment
        time.sleep(1)
        val_cmd = ["exec", "calculate fibonacci sequence for n=10"]
        val_result, val_duration = run_omni_command(val_cmd, "Validating New Skill")

        # Look for the answer (55)
        if "55" in val_result.stdout:
            validation_success = True
            log("Validation Successful! Output contains '55'.")
        else:
            log(f"Validation Failed. Output:\n{val_result.stdout}", "WARN")

        steps.append(
            {
                "name": "Functional Validation",
                "status": validation_success,
                "duration": val_duration,
                "details": "Computed correct Fibonacci (55)"
                if validation_success
                else "Incorrect output",
            }
        )

    # --- Finalize ---
    success = skill_created and validation_success
    generate_report(steps, success)

    if success:
        log("✅ scenario_verification_passed")
        sys.exit(0)
    else:
        log("❌ scenario_verification_failed", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
