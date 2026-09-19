#!/usr/bin/env python3
"""Validate the agent-governance scaffold without third-party dependencies."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "CLAUDE.md",
    "AGENTS.md",
    ".claude/rules/execution-router.md",
    ".claude/rules/agent-topology.md",
    ".claude/rules/queue-claim.md",
    ".claude/rules/tracking.md",
    ".claude/rules/git-workflow.md",
    ".claude/rules/testing-dod.md",
    ".claude/skills/execution-router/SKILL.md",
    ".claude/skills/work-tracking/SKILL.md",
    ".claude/skills/queue-claim/SKILL.md",
    ".claude/skills/review-workset/SKILL.md",
    ".agents/queue/schema/queue-item.schema.json",
    "docs/architecture/agent-workflow.md",
    "docs/queue/README.md",
    "docs/tracking/README.md",
    "docs/tracking/TEMPLATE.md",
    "docs/waiting-implement/README.md",
    "docs/waiting-implement/TEMPLATE.md",
    "scripts/agent_queue.py",
    "scripts/agent_queue_core.py",
    "scripts/agent_queue_common.py",
    "scripts/agent_queue_store.py",
    "scripts/agent_queue_claims.py",
    "tests/test_agent_queue.py",
)

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


EXCLUDED_DIRECTORIES = frozenset({
    ".git", ".agent-runtime", ".mcp-local", "node_modules", "dist",
    "coverage", "__pycache__", ".pytest_cache",
})


def source_files(suffix: str) -> Iterable[Path]:
    """Prune generated/private trees before traversal; never follow source aliases."""
    for current, directories, filenames in os.walk(ROOT, followlinks=False):
        directory = Path(current)
        directories[:] = sorted(
            name for name in directories
            if name not in EXCLUDED_DIRECTORIES
            and not (directory / name).is_symlink()
        )
        for name in sorted(filenames):
            path = directory / name
            if path.suffix == suffix and not path.is_symlink():
                yield path


def markdown_files() -> Iterable[Path]:
    yield from source_files(".md")


def validate_required_paths(errors: list[str]) -> None:
    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).exists():
            errors.append(f"Missing required path: {relative}")


EDITOR_JSONC_PATHS = frozenset({
    ".vscode/launch.json", ".vscode/settings.json",
    ".vscode/tasks.json", ".vscode/extensions.json",
})


def load_editor_jsonc(text: str) -> object:
    """Parse editor comments/trailing commas without changing strings or source files.

    All other JSON files keep the existing strict parser. This scanner is not
    JSON5: unquoted keys, single quotes, missing values and bad escapes still fail.
    """
    def string_end(value: str, start: int) -> int:
        index = start + 1
        while index < len(value):
            if value[index] == "\\":
                index += 2
            elif value[index] == '"':
                return index + 1
            else:
                index += 1
        return len(value)  # json.loads reports the unterminated string.

    chars = list(text)
    index = 0
    while index < len(text):
        if text[index] == '"':
            index = string_end(text, index)
            continue
        if text.startswith("//", index):
            ends = [position for position in (text.find("\n", index + 2), text.find("\r", index + 2)) if position >= 0]
            end = min(ends) if ends else len(text)
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise json.JSONDecodeError("Unterminated block comment", text, index)
            end += 2
        else:
            index += 1
            continue
        for position in range(index, end):
            if chars[position] not in "\r\n":
                chars[position] = " "
        index = end
    plain = "".join(chars)
    index = 0
    while index < len(plain):
        if plain[index] == '"':
            index = string_end(plain, index)
            continue
        if plain[index] == ",":
            after = index + 1
            while after < len(plain) and plain[after] in " \t\r\n":
                after += 1
            before = index - 1
            while before >= 0 and plain[before] in " \t\r\n":
                before -= 1
            if (after < len(plain) and plain[after] in "]}" and before >= 0
                    and plain[before] not in "[{,:"):
                chars[index] = " "
        index += 1
    return json.loads("".join(chars))


def validate_json(errors: list[str]) -> None:
    for path in source_files(".json"):
        try:
            text = path.read_text(encoding="utf-8")
            if path.relative_to(ROOT).as_posix() in EDITOR_JSONC_PATHS:
                load_editor_jsonc(text)
            else:
                json.loads(text)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid JSON {path.relative_to(ROOT)}: {exc}")


def validate_skills(errors: list[str]) -> None:
    skill_paths = list((ROOT / ".claude" / "skills").glob("*/SKILL.md"))
    skill_paths += list((ROOT / ".agents" / "skills").glob("*/SKILL.md"))
    for path in skill_paths:
        content = path.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(content)
        if not match:
            errors.append(f"Missing YAML frontmatter: {path.relative_to(ROOT)}")
            continue
        frontmatter = match.group(1)
        for field in ("name:", "description:"):
            if field not in frontmatter:
                errors.append(
                    f"Missing {field[:-1]} in skill frontmatter: {path.relative_to(ROOT)}"
                )


def normalize_link_target(raw: str) -> str:
    target = raw.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return target.split("#", 1)[0]


def validate_links(errors: list[str]) -> None:
    for path in markdown_files():
        content = path.read_text(encoding="utf-8")
        for raw in MARKDOWN_LINK_RE.findall(content):
            target = normalize_link_target(raw)
            if not target:
                continue
            if target.startswith(("http://", "https://", "mailto:", "skills://")):
                continue
            if target.startswith("/"):
                errors.append(
                    f"Absolute local link is forbidden in {path.relative_to(ROOT)}: {raw}"
                )
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                errors.append(
                    f"Link escapes repository in {path.relative_to(ROOT)}: {raw}"
                )
                continue
            if not resolved.exists():
                errors.append(f"Broken link in {path.relative_to(ROOT)}: {raw}")


def validate_queue_runtime_import(errors: list[str]) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from agent_queue import QueueStore  # type: ignore
    except Exception as exc:  # pragma: no cover - diagnostic path
        errors.append(f"Cannot import scripts/agent_queue.py: {exc}")
        return
    try:
        result = QueueStore(ROOT).validate_all()
    except Exception as exc:
        errors.append(f"Queue validation raised: {exc}")
        return
    for error in result.get("errors", []):
        errors.append(f"Queue: {error}")


def main() -> int:
    errors: list[str] = []
    validate_required_paths(errors)
    validate_json(errors)
    validate_skills(errors)
    validate_links(errors)
    validate_queue_runtime_import(errors)

    if errors:
        print("Agent governance validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Agent governance validation: PASS")
    print(f"- required paths: {len(REQUIRED_PATHS)}")
    print(f"- markdown files: {sum(1 for _ in markdown_files())}")
    print("- JSON: valid")
    print("- skill frontmatter: valid")
    print("- local markdown links: valid")
    print("- queue definitions: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
