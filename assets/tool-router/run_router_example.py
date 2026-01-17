import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from anthropic import Anthropic


DEFAULT_MODEL = "claude-3-5-sonnet-20240620"
LOGGER = logging.getLogger("tool_router")


@dataclass
class ToolCard:
    tool_id: str
    body: str


def load_examples(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def format_tool_card(example: Dict) -> ToolCard:
    lines = [
        f"Tool ID: {example['id']}",
        f"Intent: {example.get('intent', '').strip()}",
        f"Syntax focus: {', '.join(example.get('syntax_focus', []))}",
        f"Allowed edits: {', '.join(example.get('allowed_edits', []))}",
        f"Do NOT: {', '.join(example.get('do_not', []))}",
        f"Checks: {', '.join(example.get('checks', []))}",
    ]
    if example.get("notes"):
        lines.append(f"Notes: {example['notes']}")
    if example.get("before"):
        lines.append(f"Before: {example['before']}")
    if example.get("after"):
        lines.append(f"After: {example['after']}")
    if example.get("example"):
        lines.append(f"Example: {example['example']}")
    return ToolCard(tool_id=example["id"], body="\n".join(lines))


def build_messages(example: Dict, cards: List[ToolCard]) -> List[Dict]:
    """
    Build Claude-style router prompt following the cookbook pattern:
    - System: explain routing goal and output schema.
    - Tool cards: list each tool with capabilities/constraints.
    - User: provide the task to route.
    """
    tool_sections = "\n\n".join(card.body for card in cards)
    system = (
        "You are a tool router. Choose the single best tool for the user's task. "
        "Use the provided tool cards only. Respond with JSON only, no prose: "
        '{"tool_id": "<id>", "confidence": 0-1, "reasoning": "brief"}. '
        "Never invent tools beyond the provided IDs."
    )
    user = f"Task to route:\n{example.get('intent', '').strip()}\nAvailable tools:\n{tool_sections}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def route_example(
    client: Anthropic, model: str, example: Dict, cards: List[ToolCard]
) -> Tuple[str, float, str]:
    messages = build_messages(example, cards)
    LOGGER.debug("Routing example %s", example["id"])
    response = client.messages.create(model=model, max_tokens=256, messages=messages)
    raw_text = "".join(block.text for block in response.content if hasattr(block, "text"))
    try:
        parsed = json.loads(raw_text)
        tool_id = parsed.get("tool_id", "").strip()
        confidence = float(parsed.get("confidence", 0))
        reasoning = parsed.get("reasoning", "")
    except Exception:
        tool_id = raw_text.strip()
        confidence = 0.0
        reasoning = "Failed to parse JSON response."
    LOGGER.info(
        json.dumps(
            {
                "example_id": example["id"],
                "chosen_tool": tool_id,
                "confidence": confidence,
                "reasoning": reasoning,
            }
        )
    )
    return tool_id, confidence, reasoning


def evaluate(dataset: List[Dict], model: str, base_url: Optional[str]) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required to run routing.")

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = Anthropic(**client_kwargs)
    cards = [format_tool_card(row) for row in dataset]
    correct = 0
    for example in dataset:
        chosen, confidence, _ = route_example(client, model, example, cards)
        expected = example["id"]
        is_correct = chosen == expected
        correct += int(is_correct)
        LOGGER.info(
            json.dumps(
                {
                    "example_id": example["id"],
                    "expected": expected,
                    "chosen": chosen,
                    "confidence": confidence,
                    "correct": is_correct,
                }
            )
        )
    accuracy = correct / len(dataset) if dataset else 0
    print(f"Accuracy: {accuracy:.2%} ({correct}/{len(dataset)})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run tool-router practice set.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("tool-router/data/examples/nix.edit.jsonl"),
        help="Path to JSONL dataset.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model name to use (Claude-compatible).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Optional Anthropic-compatible base URL.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, etc).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    dataset = load_examples(args.dataset)
    base_url = args.base_url or os.environ.get("ANTHROPIC_BASE_URL")
    evaluate(dataset, args.model, base_url)


if __name__ == "__main__":
    main()
