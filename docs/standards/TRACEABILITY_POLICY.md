# Standard: Engineering Traceability Policy

> **Basis:** _HMAS Taxonomy (2025)_ and _Requirement-to-Prompt Standards (2025)_.
> **Version:** 2026.Q1

## 1. Traceability Chain Definition

This project enforces a strict "Digital Thread" across the AI engineering lifecycle. Every runtime behavior must be traceable to a source requirement.

**The Chain:**
`REQ (Requirement)` -> `SPEC (Blueprints)` -> `PROMPT (Model Instruction)` -> `TOOL (Schema/Code)` -> `TEST (Validation)`

## 2. Universal ID System

All artifacts must be prefixed with their domain:

- `REQ-SYS-*`: System-level requirements.
- `REQ-MEM-*`: Memory/LinkGraph requirements.
- `REQ-GOV-*`: Omega/Governance requirements.

## 3. The 5-Axis HMAS Audit (2025 Taxonomy)

Every new Agent or Orchestrator (like Omega) must document its position on the 5-axis taxonomy using the following JSON schema.

### 3.1 Blackboard Architecture Communication (HMAS Standard)

All inter-agent communication is conducted via **Valkey Key-Spaces** to ensure performance and isolation.

#### 3.2 Digital Thread (Valkey Stream Audit)

Every Agentic contribution must be appended to the `omni:hmas:trace` stream using the `XADD` protocol.
**Required Fields:**

- `req_id`: Global UUID for the user request.
- `agent_id`: Contributor identifier.
- `source_nodes`: List of `node_id` and their `saliency` at time of use.
- `constraints_verified`: Boolean flags for Hard Constraint compliance.

## 4. Digital Thread & Prompt Lineage

- **Evolving Orchestration:** Omega must re-calculate the Digital Thread whenever the `state_context` shifts by >20% in semantic distance.

```yaml
---
trace_id: PROMPT-OMEGA-V1
req_ref: [REQ-SYS-01, REQ-GOV-04]
eval_score: 0.92 (LLM-as-a-judge)
version: 2026.02.19
---
```

## 5. Verification Gate (3-in-1 Gate)

- A feature is not "Done" until the **3-in-1 Gate** confirms that the trace link between `TEST` and `REQ` has been empirically validated during runtime execution.
