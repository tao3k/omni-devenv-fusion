"""
filesystem/scripts/ - File System Skill Implementation

Phase 63: Migrated from tools.py to scripts pattern.
Functions are organized by responsibility:
- io.py: File I/O operations (read, write, list, search)

This __init__.py re-exports all @skill_command decorated functions
for direct access by the skill loader.
"""

from agent.skills.filesystem.scripts import io

# Re-export File I/O functions from io.py
read_file = io.read_file
write_file = io.write_file
list_directory = io.list_directory
get_file_info = io.get_file_info
save_file = io.save_file
apply_file_changes = io.apply_file_changes
