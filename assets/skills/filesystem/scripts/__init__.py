"""
filesystem/scripts/ - File System Skill Implementation

Phase 63: Migrated from tools.py to scripts pattern.
Functions are organized by responsibility:
- io.py: File I/O operations (read, write, list, search)
- ast.py: AST-based editing operations

This __init__.py re-exports all @skill_script decorated functions
for direct access by the skill loader.
"""

from agent.skills.filesystem.scripts import io
from agent.skills.filesystem.scripts import ast

# Re-export File I/O functions from io.py
read_file = io.read_file
write_file = io.write_file
list_directory = io.list_directory
search_files = io.search_files
get_file_info = io.get_file_info
save_file = io.save_file
apply_file_changes = io.apply_file_changes

# Re-export AST functions from ast.py
ast_search = ast.ast_search
ast_rewrite = ast.ast_rewrite
