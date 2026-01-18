"""
agent/core/skill_generator.py - /64 Skill Template Generator

Uses Jinja2 templates to generate new skills from the _template directory.
 Extended with LLM-driven skill generation from natural language requirements.

Supports both interactive CLI use and programmatic skill creation.
"""

from pathlib import Path
from typing import Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

import structlog

logger = structlog.get_logger(__name__)


class SkillGenerator:
    """
    Generate new skills from Jinja2 templates.

    Templates are located in `assets/skills/_template/`:
    - SKILL.md -> SKILL.md (SKILL.md.j2 also supported)
    - tools.py -> tools.py (tools.py.j2 also supported)
    - guide.md -> guide.md (guide.md.j2 also supported)
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize the generator with template directory.

        Args:
            template_dir: Path to template directory (defaults to _template)
        """
        if template_dir is None:
            # Default to _template in skills directory
            from common.gitops import get_project_root

            root = get_project_root()
            template_dir = root / "assets/skills/_template"

        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _find_template(self, name: str) -> str:
        """Find template file, checking both .j2 and plain extensions."""
        # Try .j2 first, then fall back to plain name
        if Path(self.template_dir / f"{name}.j2").exists():
            return f"{name}.j2"
        if Path(self.template_dir / name).exists():
            return name
        raise FileNotFoundError(f"Template '{name}' not found in {self.template_dir}")

    def generate(
        self,
        skill_name: str,
        description: str,
        output_dir: Path,
        author: str = "omni-dev",
        keywords: Optional[list[str]] = None,
    ) -> Path:
        """
        Generate a new skill from templates.

        Args:
            skill_name: Name of the skill (used in routing and filenames)
            description: Brief description of the skill's purpose
            output_dir: Parent directory for the new skill
            author: Author name for SKILL.md metadata
            keywords: Additional routing keywords

        Returns:
            Path to the created skill directory
        """
        skill_dir = output_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Prepare template variables
        vars = {
            "skill_name": skill_name,
            "description": description,
            "author": author,
            "keywords": keywords or [],
        }

        # Render templates (optional ones that may not exist)
        self._render_template(self._find_template("SKILL.md"), skill_dir / "SKILL.md", vars)
        self._render_template(self._find_template("tools.py"), skill_dir / "tools.py", vars)
        # README.md is optional
        try:
            self._render_template(self._find_template("README.md"), skill_dir / "README.md", vars)
        except FileNotFoundError:
            pass  # README.md is optional

        return skill_dir

    def _render_template(self, template_name: str, output_path: Path, vars: dict) -> None:
        """
        Render a single template and write to file.

        Args:
            template_name: Name of the template file
            output_path: Path to write the rendered content
            vars: Variables to pass to the template
        """
        template = self.env.get_template(template_name)
        content = template.render(**vars)
        output_path.write_text(content)

    def generate_from_template(self, skill_name: str, description: str) -> Path:
        """
        Convenience method to generate a skill in the default skills directory.

        Args:
            skill_name: Name of the skill
            description: Brief description

        Returns:
            Path to the created skill
        """
        from common.skills_path import SKILLS_DIR

        skills_dir = SKILLS_DIR()
        return self.generate(skill_name, description, skills_dir)


# Convenience function for CLI use
def create_skill(
    skill_name: str,
    description: str,
    author: str = "omni-dev",
    keywords: Optional[list[str]] = None,
) -> Path:
    """
    Create a new skill from templates.

    Args:
        skill_name: Name of the skill
        description: Brief description of the skill's purpose
        author: Author name for SKILL.md metadata
        keywords: Additional routing keywords

    Returns:
        Path to the created skill directory
    """
    generator = SkillGenerator()
    return generator.generate(
        skill_name, description, generator.template_dir.parent, author, keywords
    )


# =============================================================================
#  LLM-Driven Skill Generation
# =============================================================================


class LLMSkillGenerator:
    """
     LLM-Driven Skill Generator.
     Added self-repair loop with validation and refinement.

    Uses LLM to analyze natural language requirements and generate
    complete skill implementations automatically. Validates and refines
    code until tests pass using the Meta skill.
    """

    def __init__(
        self,
        inference_client: Optional[Any] = None,
        skill_manager: Optional[Any] = None,
        max_validation_retries: int = 2,
    ):
        """
        Initialize the LLM-driven generator.

        Args:
            inference_client: LLM inference client (defaults to global client)
            skill_manager: SkillContext instance for calling meta.refine_code
            max_validation_retries: Maximum validation/refinement attempts
        """
        self.inference = inference_client
        self.skill_manager = skill_manager
        self.template_generator = SkillGenerator()
        self.max_validation_retries = max_validation_retries

    async def generate_from_requirement(
        self,
        requirement: str,
        output_dir: Optional[Path] = None,
        validate: bool = True,
    ) -> dict[str, Any]:
        """
        Generate a complete skill from a natural language requirement.

         Added optional validation and self-repair loop.

        Args:
            requirement: User's natural language requirement
            output_dir: Directory to create skill in (defaults to SKILLS_DIR)
            validate: Whether to validate and refine generated code

        Returns:
            Dict with:
                - skill_name: Generated skill name
                - description: Skill description
                - commands: List of command definitions
                - path: Path to created skill directory
                - success: Whether generation succeeded
                - validated: Whether validation passed (if requested)
                - validation_attempts: Number of validation attempts
        """
        from agent.core.meta_agent.prompt import (
            MetaAgentPrompt,
            extract_json_from_response,
        )

        # Step 1: Get LLM to analyze requirement and generate skill spec
        prompt = MetaAgentPrompt.skill_generation(requirement)

        try:
            if self.inference is None:
                from agent.core.inference import get_inference

                self.inference = get_inference()

            response = await self.inference.chat(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Generate the skill specification JSON."},
                ],
                temperature=0.2,
            )

            skill_spec = extract_json_from_response(response.content)

        except Exception as e:
            logger.error("llm_skill_generation_failed", error=str(e))
            return {
                "success": False,
                "error": f"LLM generation failed: {e}",
            }

        # Step 2: Extract skill specification
        skill_name = skill_spec.get("skill_name", "").lower().replace("_", "-")
        description = skill_spec.get("description", "")
        routing_keywords = skill_spec.get("routing_keywords", [])
        commands = skill_spec.get("commands", [])

        if not skill_name:
            return {"success": False, "error": "Skill name is required"}

        # Step 3: Generate skill files using template generator
        if output_dir is None:
            from common.skills_path import SKILLS_DIR

            output_dir = SKILLS_DIR()

        try:
            skill_path = self.template_generator.generate(
                skill_name=skill_name,
                description=description,
                output_dir=output_dir,
                author="meta-agent",
                keywords=routing_keywords,
            )
        except Exception as e:
            logger.error("skill_template_generation_failed", error=str(e))
            return {
                "success": False,
                "error": f"Template generation failed: {e}",
            }

        # Step 4: Generate command implementations
        command_count = 0
        for cmd in commands:
            try:
                self._write_command_implementation(skill_path, cmd)
                command_count += 1
            except Exception as e:
                logger.warning(
                    "command_implementation_failed",
                    command=cmd.get("name"),
                    error=str(e),
                )

        # Step 5: Validate and refine
        validated = False
        validation_attempts = 1

        if validate and command_count > 0:
            logger.info(
                "validating_generated_skill",
                skill_name=skill_name,
                commands=command_count,
            )

            try:
                from agent.core.meta_agent.validator import validate_and_refine

                # Collect all command code for validation
                scripts_init = skill_path / "scripts" / "__init__.py"
                if scripts_init.exists():
                    skill_code = scripts_init.read_text()
                else:
                    skill_code = ""

                # Generate test code
                test_code = self._generate_test_code(skill_name, commands)

                # Run validation and refinement loop
                validation_result = await validate_and_refine(
                    skill_name=skill_name,
                    skill_code=skill_code,
                    test_code=test_code,
                    requirement=requirement,
                    skill_manager=self.skill_manager,
                    max_retries=self.max_validation_retries,
                )

                if validation_result.get("success"):
                    # Write refined code back
                    refined_code = validation_result.get("code", "")
                    if refined_code and scripts_init.exists():
                        scripts_init.write_text(refined_code)
                    validated = True
                    logger.info(
                        "skill_validation_passed",
                        skill_name=skill_name,
                        attempts=validation_result.get("attempts", 1),
                    )
                else:
                    logger.warning(
                        "skill_validation_failed",
                        skill_name=skill_name,
                        error=validation_result.get("error", "Unknown error")[:200],
                    )

                validation_attempts = validation_result.get("attempts", 1)

            except Exception as e:
                logger.error("validation_error", skill_name=skill_name, error=str(e))

        logger.info(
            "skill_generated",
            skill_name=skill_name,
            command_count=command_count,
            path=str(skill_path),
            validated=validated,
        )

        return {
            "success": True,
            "skill_name": skill_name,
            "description": description,
            "routing_keywords": routing_keywords,
            "commands": [c.get("name") for c in commands],
            "command_count": command_count,
            "path": str(skill_path),
            "validated": validated,
            "validation_attempts": validation_attempts,
        }

    def _generate_test_code(self, skill_name: str, commands: list[dict]) -> str:
        """
        Generate basic pytest test code for the skill.

        Args:
            skill_name: Name of the skill
            commands: List of command specifications

        Returns:
            Python test code as string
        """
        test_funcs = []
        for cmd in commands:
            cmd_name = cmd.get("name", "").replace("-", "_")
            description = cmd.get("description", "")

            test_func = f'''
async def test_{cmd_name}():
    """Test {description or cmd_name}."""
    # TODO: Implement meaningful test
    from scripts.{skill_name} import {cmd_name}
    result = await {cmd_name}()
    assert result.get("success") == True, f"Expected success, got: {{result}}"
'''
            test_funcs.append(test_func)

        # Build imports
        imports = '"""Tests for {skill_name} skill."""\n\nimport pytest\n\n'
        imports = imports.replace("{skill_name}", skill_name)

        # Build test class or module
        test_content = imports + "\n".join(test_funcs)

        return test_content

    def _write_command_implementation(
        self,
        skill_path: Path,
        command: dict[str, Any],
    ) -> None:
        """
        Write command implementation to scripts/__init__.py.

        Args:
            skill_path: Path to the skill directory
            command: Command specification from LLM
        """
        import re

        name = command.get("name", "").replace("-", "_")
        description = command.get("description", "")
        implementation = command.get("implementation", "")
        parameters = command.get("parameters", [])

        # Build function signature
        required_params = []
        optional_params = []

        for param in parameters:
            p_name = param.get("name", "").replace("-", "_")
            p_type = param.get("type", "str")
            p_required = param.get("required", False)

            if p_required:
                required_params.append(f"{p_name}: {p_type}")
            else:
                default = '""' if p_type == "str" else "None"
                optional_params.append(f"{p_name}: {p_type} = {default}")

        all_params = required_params + optional_params
        params_str = ", ".join(all_params) if all_params else ""

        # Clean up implementation (remove imports that shouldn't be there)
        impl_lines = implementation.split("\n")
        cleaned_impl = []
        for line in impl_lines:
            # Skip import statements in function body
            if line.strip().startswith(("import ", "from ")):
                continue
            cleaned_impl.append(line)

        impl_body = "\n".join(cleaned_impl).strip()
        if not impl_body:
            impl_body = 'return {"success": True, "data": {}, "error": ""}'

        # Build function code
        func_code = f'''
def {name}({params_str}) -> dict[str, Any]:
    """
    {description}

    Args:
        {chr(10) + "        ".join([f"{p.get('name')}: {p.get('description')}" for p in parameters])}
    """
    {impl_body.replace(chr(10), chr(10) + "    ")}
'''

        # Append to scripts/__init__.py
        scripts_init = skill_path / "scripts" / "__init__.py"
        existing_content = scripts_init.read_text() if scripts_init.exists() else ""

        # Add function before the __all__ export
        if "__all__" in existing_content:
            idx = existing_content.find("__all__")
            existing_content = existing_content[:idx] + func_code + "\n\n" + existing_content[idx:]
        else:
            existing_content += func_code

        # Update __all__ to include new command
        all_match = re.search(r"__all__\s*=\s*\[([^\]]*)\]", existing_content, re.DOTALL)
        if all_match:
            current_all = all_match.group(1)
            if f'"{name}"' not in current_all:
                # Add to __all__
                new_all = current_all.rstrip().rstrip(",")
                if new_all:
                    new_all += f', "{name}"\n'
                else:
                    new_all = f'    "{name}",\n'
                existing_content = existing_content.replace(
                    f"__all__ = [{current_all}]",
                    f"__all__ = [{new_all}]",
                )

        scripts_init.write_text(existing_content)


async def generate_skill_from_requirement(
    requirement: str,
    output_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Convenience function to generate a skill from natural language requirement.

    Args:
        requirement: User's natural language requirement
        output_dir: Directory to create skill in

    Returns:
        Dict with generation result
    """
    generator = LLMSkillGenerator()
    return await generator.generate_from_requirement(requirement, output_dir)
