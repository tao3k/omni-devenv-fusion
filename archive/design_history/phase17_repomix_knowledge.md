# Phase 17: Repomix-Powered Knowledge Base

**Status**: Proposed
**Type**: Architecture Enhancement
**Owner**: KnowledgeIngestor
**Vision**: Use repomix to simplify and standardize knowledge ingestion

## 1. Problem Statement

**The Pain: Custom File Parsing Logic**

Current `KnowledgeIngestor`:

- Recursively traverses directories
- Parses markdown files manually
- Handles keyword extraction
- Formats output for vector store

This is reinventing the wheel - `repomix` does all this better.

## 2. The Solution: Repomix Integration

Replace custom file processing with `repomix` CLI:

```
Knowledge Directories
        ↓
   repomix CLI
        ↓
   project_knowledge.xml
        ↓
   KnowledgeIngestor (parse XML only)
        ↓
   VectorStore
```

## 3. Architecture Specification

### 3.1 Repomix Configuration

```json
// agent/knowledge/repomix.json
{
  "output": {
    "filePath": "project_knowledge.xml",
    "style": "xml",
    "headerText": "Project Knowledge Base for Omni-DevEnv"
  },
  "include": ["**/*.md"],
  "includeFiles": ["**/*.md"],
  "ignore": {
    "useGitignore": true,
    "additionalPatterns": ["test", "template", "draft"]
  }
}
```

### 3.2 Lefthook Integration

```yaml
# .lefthook/pre-commit or post-merge
pre-commit:
  commands:
    update-knowledge-xml:
      glob: "agent/knowledge/**/*.md"
      run: |
        cd agent/knowledge
        repomix --config repomix.json --output project_knowledge.xml
```

### 3.3 Simplified KnowledgeIngestor

```python
import xml.etree.ElementTree as ET
from pathlib import Path

class KnowledgeIngestor:
    async def ingest_from_repomix(
        self,
        xml_path: str = "agent/knowledge/project_knowledge.xml"
    ) -> dict:
        """
        Parse repomix XML and ingest into VectorStore.

        Repomix XML format:
        <files>
          <file path="path/to/file.md">content</file>
        </files>
        """
        if not Path(xml_path).exists():
            return {"success": False, "error": f"XML not found: {xml_path}"}

        tree = ET.parse(xml_path)
        root = tree.getroot()

        results = []
        for file_node in root.findall(".//file"):
            path = file_node.get("path")
            content = file_node.text or ""

            if not content.strip():
                continue

            # Extract title from first H1
            title = content.split('\n')[0].lstrip('# ').strip()

            # Generate ID
            file_id = Path(path).stem.lower().replace('-', '_')

            # Ingest into vector store
            success = await self.vector_store.add(
                documents=[content],
                ids=[f"knowledge-{file_id}"],
                collection="project_knowledge",
                metadatas=[{
                    "domain": "knowledge",
                    "title": title,
                    "source_file": path,
                }]
            )

            results.append({"path": path, "success": success})

        successful = sum(1 for r in results if r["success"])
        return {
            "success": successful == len(results),
            "total": len(results),
            "ingested": successful,
            "failed": len(results) - successful,
        }
```

## 4. Benefits

| Aspect          | Before (Custom)  | After (Repomix) |
| --------------- | ---------------- | --------------- |
| File traversal  | Manual recursion | Built-in        |
| XML format      | Custom           | Standardized    |
| Token counting  | Manual           | Built-in        |
| .gitignore      | Manual           | Auto-respected  |
| Code complexity | ~150 lines       | ~50 lines       |
| Maintainability | Low              | High            |

## 5. Implementation Plan

### Step 1: Add repomix config

- [ ] Create `agent/knowledge/repomix.json`
- [ ] Test XML output

### Step 2: Integrate with lefthook

- [ ] Add hook to auto-regenerate XML
- [ ] Test hook triggers correctly

### Step 3: Simplify KnowledgeIngestor

- [ ] Refactor `ingest_from_repomix()` method
- [ ] Remove custom directory traversal
- [ ] Keep settings.yaml support for config

### Step 4: Testing

- [ ] Test XML parsing
- [ ] Test vector store ingestion
- [ ] Verify hook triggers

## 6. Related Documentation

- [Repomix GitHub](https://github.com/yusongh/repomix)
- `agent/capabilities/knowledge_ingestor.py` - Current implementation
- `agent/knowledge/repomix.json` - Configuration
