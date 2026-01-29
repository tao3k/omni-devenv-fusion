"smart_ast/engine.py"

import subprocess
import json
import os
import tempfile
from typing import Optional, Union
from . import patterns


class SmartAstEngine:
    def __init__(self):
        self.rules_dir = os.path.join(os.path.dirname(__file__), "rules")
        if not os.path.exists(self.rules_dir):
            os.makedirs(self.rules_dir)

    def execute(
        self,
        query: str,
        path: str = ".",
        mode: str = "auto",
        language: Optional[str] = None,
        rewrite: Optional[str] = None,
        dry_run: bool = True,
    ):
        """
        Public entry point for AST operations.
        """
        # 1. Resolution Layer
        resolved_query = query
        resolved_mode = mode
        resolved_rule_file = None
        resolved_lang = language

        if mode == "auto":
            # Check for named rule files
            rule_path = os.path.join(self.rules_dir, f"{query}.yaml")
            if os.path.exists(rule_path):
                resolved_mode = "rule"
                resolved_rule_file = rule_path
            else:
                target_lang = (language or "").lower()

                # Special handling for Rust visibility shorthands
                if target_lang == "rust" or not target_lang:
                    if query in ("structs", "struct"):
                        resolved_query = 'id: find-structs\nlanguage: rust\nrule:\n  any:\n    - pattern: "pub struct $NAME"\n    - pattern: "struct $NAME"'
                        resolved_mode = "rule"
                    elif query in ("functions", "function"):
                        resolved_query = 'id: find-fns\nlanguage: rust\nrule:\n  any:\n    - pattern: "pub fn $NAME($$$) { $$$ }"\n    - pattern: "fn $NAME($$$) { $$$ }"'
                        resolved_mode = "rule"

                if resolved_mode == "auto":
                    # Check for semantic shorthands in patterns.py
                    shorthand_found = False
                    if target_lang in patterns.LANG_PATTERNS:
                        if query in patterns.LANG_PATTERNS[target_lang]:
                            resolved_query = patterns.LANG_PATTERNS[target_lang][query]
                            resolved_mode = "pattern"
                            shorthand_found = True

                    if not shorthand_found and not target_lang:
                        for lang, p_map in patterns.LANG_PATTERNS.items():
                            if query in p_map:
                                resolved_query = p_map[query]
                                resolved_mode = "pattern"
                                resolved_lang = lang
                                break

        # 2. Execution Layer
        return self._run_ast_grep(
            query=resolved_query,
            path=path,
            mode=resolved_mode,
            language=resolved_lang,
            rewrite=rewrite,
            rule_file=resolved_rule_file,
            dry_run=dry_run,
        )

    def _run_ast_grep(
        self,
        query: str,
        path: str,
        mode: str,
        language: Optional[str] = None,
        rewrite: Optional[str] = None,
        rule_file: Optional[str] = None,
        dry_run: bool = True,
    ):
        # Decide command
        use_scan = (
            (mode == "rule")
            or ("rule:" in query)
            or (rule_file is not None)
            or (rewrite is not None)
        )

        cmd = ["ast-grep"]
        if use_scan:
            cmd.append("scan")
        else:
            cmd.append("run")

        cmd.append("--json=stream")

        temp_rule_file = None
        try:
            if use_scan:
                if rule_file and not rewrite:
                    cmd.extend(["--rule", rule_file])
                else:
                    # Dynamically construct rule (with fix if needed)
                    if rewrite:
                        rule_content = f"id: dynamic-rewrite\nlanguage: {language or 'python'}\nrule:\n  pattern: |\n    {query}\nfix: |\n  {rewrite}\n"
                    elif "id:" in query or "rule:" in query:
                        rule_content = (
                            query.replace("rule:", "", 1).strip()
                            if query.startswith("rule:")
                            else query
                        )
                    else:
                        rule_content = f"id: generated-rule\nlanguage: {language or 'python'}\nrule:\n  {query}\n"

                    temp_rule_file = tempfile.NamedTemporaryFile(
                        mode="w", suffix=".yaml", delete=False
                    )
                    temp_rule_file.write(rule_content)
                    temp_rule_file.close()
                    cmd.extend(["--rule", temp_rule_file.name])
            else:
                # RUN MODE (Search patterns)
                cmd.extend(["--pattern", query])
                if language:
                    cmd.extend(["--lang", language])

            cmd.append(path)

            try:
                process = subprocess.run(cmd, capture_output=True, text=True, check=False)

                if process.returncode != 0 and process.stderr:
                    safe_cmd = [str(c) for c in cmd]
                    return (
                        f"Error executing ast-grep: {process.stderr}\nCommand: {' '.join(safe_cmd)}"
                    )

                results = []
                for line in process.stdout.strip().split("\n"):
                    if not line:
                        continue
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

                if not results:
                    return f"[No matches found for '{query}' in {path}]"

                if rewrite and not dry_run:
                    # MANUAL APPLY: Use byteOffset from JSON
                    files_to_update = {}
                    for r in results:
                        f_path = r.get("file")
                        if not f_path or "replacement" not in r:
                            continue

                        if f_path not in files_to_update:
                            files_to_update[f_path] = []
                        # Use byteOffset structure from ast-grep output
                        byte_range = r.get("range", {}).get("byteOffset", {})
                        if "start" in byte_range and "end" in byte_range:
                            files_to_update[f_path].append(
                                (byte_range["start"], byte_range["end"], r["replacement"])
                            )

                    applied_count = 0
                    for f_path, replacements in files_to_update.items():
                        replacements.sort(key=lambda x: x[0], reverse=True)
                        try:
                            with open(f_path, "r") as f:
                                content = f.read()
                            for start, end, new_text in replacements:
                                # Standard Python string slicing works if we use byte indices carefully
                                # But wait, Python strings are UTF-16 internally. Let's use bytes for accuracy.
                                with open(f_path, "rb") as f_bin:
                                    b_content = f_bin.read()
                                for start, end, new_text in replacements:
                                    b_content = (
                                        b_content[:start]
                                        + new_text.encode("utf-8")
                                        + b_content[end:]
                                    )
                                with open(f_path, "wb") as f_bin:
                                    f_bin.write(b_content)
                            applied_count += 1
                        except Exception as e:
                            return f"Failed to update file {f_path}: {e}"

                    return f"Successfully applied transformation to {applied_count} files."

                return self._format_results(results, query, path, is_rewrite=bool(rewrite))
            except Exception as e:
                safe_cmd = [str(c) for c in cmd]
                return f"Execution error: {e}\nCommand: {' '.join(safe_cmd)}"

        finally:
            if temp_rule_file and os.path.exists(temp_rule_file.name):
                os.unlink(temp_rule_file.name)

    def _format_results(self, results, query, path, is_rewrite=False):
        title = "TRANSFORMATION PREVIEW" if is_rewrite else "SMART AST SEARCH"
        output = [
            f"// {title}: {path}",
            f"// Query: {query}",
            f"// Total matches: {len(results)}\n",
        ]

        current_file = None
        for r in results:
            file_path = r.get("file", "unknown")
            if file_path != current_file:
                current_file = file_path
                output.append(f"\n// File: {current_file}")

            line_num = r.get("range", {}).get("start", {}).get("line", 0) + 1
            text = r.get("text", "").strip().split("\n")[0]

            if is_rewrite and "replacement" in r:
                repl = r["replacement"].strip().split("\n")[0]
                output.append(f"L{line_num:<4} [MATCH] {text}")
                output.append(f"      [REPLACE] {repl}")
            else:
                if "\n" in r.get("text", ""):
                    text += " ..."
                output.append(f"L{line_num:<4} {text}")

        return "\n".join(output)
