"""
test_smart_ast_unified.py - Unified tests for code_tools.smart_ast

Tests the new SmartAstEngine and the unified smart_ast command which
combines search, refactor, and modular rule capabilities.
"""

import os
import pytest
from assets.skills.code_tools.scripts.smart_ast.engine import SmartAstEngine


@pytest.fixture
def engine():
    return SmartAstEngine()


@pytest.fixture
def sample_workspace(tmp_path):
    """Create a temporary workspace with multi-language files and ast-grep config."""
    # Create sgconfig.yml
    config = tmp_path / "sgconfig.yml"
    config.write_text("""
ruleDirs: [rules]
""")
    (tmp_path / "rules").mkdir()

    # Python
    py_file = tmp_path / "app.py"
    py_file.write_text("""
class UserService:
    def get_user(self, id):
        print(f"Getting user {id}")
        return {"id": id, "name": "Test"}

def main():
    service = UserService()
    service.get_user(1)
    print("Done")
""")

    # Rust
    rs_file = tmp_path / "lib.rs"
    rs_file.write_text("""
pub struct Config {
    pub port: u16,
}

struct Internal {
    secret: String,
}

pub fn start(cfg: Config) {
    println!("Starting on port {}", cfg.port);
}

fn private_helper() {}
""")

    # JS/TS
    ts_file = tmp_path / "component.ts"
    ts_file.write_text("""
interface Props {
  name: string;
}

export class Greeter {
  greet(props: Props) {
    console.log(`Hello, ${props.name}`);
  }
}
""")

    return tmp_path


class TestSmartAstUnified:
    """Tests for the unified SmartAstEngine."""

    def test_semantic_shorthand_python(self, engine, sample_workspace):
        """Test 'classes' shorthand for Python."""
        result = engine.execute("classes", str(sample_workspace), language="python")
        assert "UserService" in result
        assert "L2" in result

    def test_semantic_shorthand_rust(self, engine, sample_workspace):
        """Test 'structs' shorthand for Rust (uses 'any' rule for pub/private)."""
        result = engine.execute("structs", str(sample_workspace), language="rust")
        assert "Config" in result
        assert "Internal" in result
        assert "Total matches: 2" in result

    def test_structural_search_pattern(self, engine, sample_workspace):
        """Test raw AST pattern search."""
        result = engine.execute("print($$$)", str(sample_workspace), language="python")
        assert 'print(f"Getting user {id}")' in result
        assert 'print("Done")' in result

    def test_modular_rule_search(self, engine, sample_workspace):
        """Test using a named rule from the rules/ directory."""
        # unsafe_rust.yaml should have been created in previous steps
        result = engine.execute("unsafe_rust", str(sample_workspace))
        assert "[No matches found" in result

    def test_structural_rewrite_preview(self, engine, sample_workspace):
        """Test previewing a structural replacement (dry_run=True)."""
        result = engine.execute(
            query="print($MSG)",
            path=str(sample_workspace),
            rewrite="logger.info($MSG)",
            dry_run=True,
            language="python",
        )
        assert "TRANSFORMATION PREVIEW" in result
        assert '[MATCH] print(f"Getting user {id}")' in result
        assert '[REPLACE] logger.info(f"Getting user {id}")' in result

        # Verify file is NOT changed
        content = (sample_workspace / "app.py").read_text()
        assert "print(" in content
        assert "logger.info" not in content

    def test_structural_rewrite_apply(self, engine, sample_workspace):
        """Test applying a structural replacement (dry_run=False)."""
        # Ensure we target the directory
        result = engine.execute(
            query="print($MSG)",
            path=str(sample_workspace),
            rewrite="logger.info($MSG)",
            dry_run=False,
            language="python",
        )
        assert "Successfully applied" in result

        # Verify file IS changed
        py_file = sample_workspace / "app.py"
        content = py_file.read_text()
        assert "logger.info" in content
        assert "print(" not in content

    def test_rule_search_inline(self, engine, sample_workspace):
        """Test inline YAML rule."""
        # A more standard rule using 'kind' to satisfy the engine
        rule = """
id: find-service
language: python
rule:
  kind: class_definition
  pattern: "class UserService: $$$"
"""
        result = engine.execute(rule, str(sample_workspace), mode="rule")
        assert "UserService" in result
        assert "Total matches: 1" in result

    def test_language_detection(self, engine, sample_workspace):
        """Test that it detects language from extension if not provided."""
        # interface is TS/JS specific shorthand
        result = engine.execute("interfaces", str(sample_workspace / "component.ts"))
        assert "interface Props" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
