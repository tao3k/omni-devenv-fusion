# Skill Manager - Commands Guide

This skill provides commands for discovering, installing, and managing other skills.

## Commands

### `skill.discover`

Search the known skills index for matching skills.

**Usage:**

```
@omni("skill.discover", {"query": "docker", "limit": 5})
```

**Examples:**

- `skill.discover("data analysis")` - Find data-related skills
- `skill.discover("network")` - Find network-related skills
- `skill.discover("")` - List all skills

---

### `skill.suggest`

Get skill suggestions based on your task description.

**Usage:**

```
@omni("skill.suggest", {"task": "analyze pcap file"})
```

**Examples:**

- `skill.suggest("work with docker containers")`
- `skill.suggest("data manipulation and analysis")`
- `skill.suggest("video transcoding")`

---

### `skill.jit_install`

Install and load a skill from the known index.

**Usage:**

```
@omni("skill.jit_install", {"skill_id": "pandas-expert"})
```

**Examples:**

- `skill.jit_install("docker-ops")` - Install Docker skill
- `skill.jit_install("network-analysis")` - Install Network Analysis skill
- `skill.jit_install("pandas-expert", {"auto_load": false})` - Install without loading

---

### `skill.list_index`

List all skills in the known skills index.

**Usage:**

```
@omni("skill.list_index")
```

---

## Workflow

### Finding a Skill for a New Task

1. **Describe your task:**

   ```
   @omni("skill.suggest", {"task": "I need to analyze pcap files"})
   ```

2. **Review suggestions:**
   - System returns matching skills with descriptions

3. **Install the best match:**

   ```
   @omni("skill.jit_install", {"skill_id": "network-analysis"})
   ```

4. **Use the new skill:**
   ```
   @omni("network.pcap_analyze", {"file": "capture.pcap"})
   ```

---

## Tips

- Use keywords like "docker", "pandas", "network" for better search results
- The `skill_id` is the unique identifier (e.g., "pandas-expert", not "Pandas Expert")
- After installation, the skill is automatically loaded and ready to use
