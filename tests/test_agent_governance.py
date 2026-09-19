"""Regression checks for source-only governance discovery in a pnpm workspace."""
from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "scripts"))
import validate_agent_governance as governance


class SourceDiscoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        private = REPOSITORY / ".mcp-local"
        private.mkdir(mode=0o700, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="governance-test-", dir=private)
        self.scratch = Path(self.temporary.name)
        self.root = self.scratch / "workspace"
        self.root.mkdir()
        self.root_patch = patch.object(governance, "ROOT", self.root)
        self.root_patch.start()

    def tearDown(self) -> None:
        self.root_patch.stop()
        self.temporary.cleanup()

    def put(self, path: str, content: str) -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def test_discovers_source_including_hidden_governance(self) -> None:
        for path in ["package.json", ".agents/queue/items/Q0001.json", ".claude/settings.json", "packages/example/package.json"]:
            self.put(path, "{}")
        actual = {str(path.relative_to(self.root)) for path in governance.source_files(".json")}
        self.assertEqual(actual, {"package.json", ".agents/queue/items/Q0001.json", ".claude/settings.json", "packages/example/package.json"})

    def test_prunes_generated_and_private_trees_before_validation(self) -> None:
        self.put("README.md", "Valid source")
        self.put("package.json", "{}")
        for directory in governance.EXCLUDED_DIRECTORIES:
            self.put(f"{directory}/nested/invalid.json", "not json")
            self.put(f"{directory}/nested/README.md", "[broken](/outside)")
        errors: list[str] = []
        governance.validate_json(errors)
        governance.validate_links(errors)
        self.assertEqual(errors, [])
        self.assertEqual([path.name for path in governance.markdown_files()], ["README.md"])

    def test_still_reports_invalid_repository_json(self) -> None:
        self.put("packages/example/package.json", "not json")
        errors: list[str] = []
        governance.validate_json(errors)
        self.assertTrue(any("packages/example/package.json" in error for error in errors))

    def test_still_reports_broken_source_links(self) -> None:
        self.put("docs/README.md", "[missing](missing.md)")
        errors: list[str] = []
        governance.validate_links(errors)
        self.assertTrue(any("Broken link" in error for error in errors))

    def test_does_not_follow_file_or_directory_symlinks(self) -> None:
        outside = self.scratch / "outside"
        outside.mkdir()
        (outside / "invalid.json").write_text("not json", encoding="utf-8")
        (self.root / "alias").symlink_to(outside, target_is_directory=True)
        (self.root / "alias.json").symlink_to(outside / "invalid.json")
        self.assertEqual(list(governance.source_files(".json")), [])

    def test_invalid_utf8_source_is_a_validation_error(self) -> None:
        (self.root / "invalid.json").write_bytes(b"\xff")
        errors: list[str] = []
        governance.validate_json(errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid JSON invalid.json", errors[0])

    def test_enumeration_is_deterministic_and_required_paths_remain_required(self) -> None:
        for name in ["z.json", "a.json", "m.json"]:
            self.put(name, "{}")
        self.assertEqual([path.name for path in governance.source_files(".json")], ["a.json", "m.json", "z.json"])
        errors: list[str] = []
        governance.validate_required_paths(errors)
        self.assertTrue(any("CLAUDE.md" in error for error in errors))

    def test_editor_jsonc_comments_and_trailing_commas(self) -> None:
        for path in governance.EDITOR_JSONC_PATHS:
            self.put(path, '{// note\n"items": [1, 2,], /* block */ "enabled": true,}')
        errors: list[str] = []
        governance.validate_json(errors)
        self.assertEqual(errors, [])

    def test_editor_jsonc_preserves_comment_markers_inside_strings(self) -> None:
        value = {"url": "https://example.invalid/a//b", "glob": "**/*", "syntax": ",}", "quote": 'a"b', "slash": "\\"}
        self.assertEqual(governance.load_editor_jsonc(json.dumps(value)), value)

    def test_editor_jsonc_preserves_unicode_and_escaped_quotes(self) -> None:
        value = {"text": 'ภาษาไทย 👩🏽‍💻 \\" // not a comment', "path": "C:\\tools\\a"}
        text = '/* comment */' + json.dumps(value, ensure_ascii=True) + '// tail'
        self.assertEqual(governance.load_editor_jsonc(text), value)

    def test_editor_jsonc_does_not_change_original_file(self) -> None:
        original = '{ // user settings\n"configurations": [],\n}'
        path = self.put(".vscode/launch.json", original)
        errors: list[str] = []
        governance.validate_json(errors)
        self.assertEqual(errors, [])
        self.assertEqual(path.read_text(), original)

    def test_non_editor_system_json_remains_strict(self) -> None:
        for path in ["package.json", ".agents/queue/items/Q0001.json", "docs/runtime/tool-catalog.json"]:
            self.put(path, '{// invalid here\n"a": 1,}')
        errors: list[str] = []
        governance.validate_json(errors)
        self.assertEqual(len(errors), 3)

    def test_nonallowlisted_editor_or_nested_json_remains_strict(self) -> None:
        for path in [".vscode/custom.json", "packages/a/.vscode/launch.json"]:
            self.put(path, '{/* invalid here */ "a":1,}')
        errors: list[str] = []
        governance.validate_json(errors)
        self.assertEqual(len(errors), 2)

    def test_invalid_editor_json_still_fails(self) -> None:
        for text in ['{unquoted:1}', "{'single':1}", '{"a":}', '[1,,]', '[,]', '{,}', '{"a":,}', '{"a":1,,}', '{"a":1]']:
            with self.subTest(text=text):
                with self.assertRaises(json.JSONDecodeError):
                    governance.load_editor_jsonc(text)

    def test_unterminated_comments_and_strings_fail(self) -> None:
        for text in ['{/* never closed', '{"a":"unterminated //not comment}', '[1] /* never closed']:
            with self.subTest(text=text):
                with self.assertRaises(json.JSONDecodeError):
                    governance.load_editor_jsonc(text)

    def test_comment_removal_never_joins_separate_tokens(self) -> None:
        for text in ['[1/*gap*/2]', '[tru/*gap*/e]', '{"a"/*gap*/"b"}']:
            with self.subTest(text=text):
                with self.assertRaises(json.JSONDecodeError):
                    governance.load_editor_jsonc(text)

    def test_comments_between_trailing_comma_and_close(self) -> None:
        for newline in ["\n", "\r", "\r\n"]:
            self.assertEqual(governance.load_editor_jsonc('{// comment' + newline + '"a":1,}'), {"a": 1})
        self.assertEqual(governance.load_editor_jsonc('{"a":[1,/*x*/],/*y*/}'), {"a": [1]})
        self.assertEqual(governance.load_editor_jsonc('["a,]", // comment\n]'), ["a,]"])

    def test_invalid_editor_encoding_is_reported(self) -> None:
        path = self.put(".vscode/launch.json", "{}")
        path.write_bytes(b"\xff")
        errors: list[str] = []
        governance.validate_json(errors)
        self.assertEqual(len(errors), 1)
        self.assertIn(".vscode/launch.json", errors[0])


if __name__ == "__main__":
    unittest.main()
