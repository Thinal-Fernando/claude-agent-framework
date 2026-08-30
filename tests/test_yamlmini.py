"""Tests for the dependency-free YAML-subset parser."""

import unittest

from supervisor.yamlmini import YamlError, parse


class TestScalars(unittest.TestCase):
    def test_types(self):
        data = parse(
            "a: 1\n"
            "b: 2.5\n"
            "c: true\n"
            "d: false\n"
            "e: null\n"
            "f: hello\n"
            'g: "quoted"\n'
            "h: 'single'\n"
        )
        self.assertEqual(data["a"], 1)
        self.assertEqual(data["b"], 2.5)
        self.assertIs(data["c"], True)
        self.assertIs(data["d"], False)
        self.assertIsNone(data["e"])
        self.assertEqual(data["f"], "hello")
        self.assertEqual(data["g"], "quoted")
        self.assertEqual(data["h"], "single")

    def test_quoted_version_stays_a_string(self):
        self.assertEqual(parse('version: "0.4.0"')["version"], "0.4.0")

    def test_empty_value_is_none(self):
        self.assertIsNone(parse("key:")["key"])

    def test_empty_document(self):
        self.assertEqual(parse(""), {})
        self.assertEqual(parse("# only a comment\n\n"), {})


class TestComments(unittest.TestCase):
    def test_trailing_comment_removed(self):
        self.assertEqual(parse("a: 1  # trailing")["a"], 1)

    def test_hash_inside_quotes_preserved(self):
        self.assertEqual(parse('a: "has # hash"')["a"], "has # hash")

    def test_full_line_comment_skipped(self):
        self.assertEqual(parse("# note\na: 1\n")["a"], 1)


class TestNesting(unittest.TestCase):
    def test_nested_mappings(self):
        data = parse("session:\n  model: sonnet\n  limits:\n    turns: 30\n")
        self.assertEqual(data["session"]["model"], "sonnet")
        self.assertEqual(data["session"]["limits"]["turns"], 30)

    def test_sibling_blocks_keep_own_values(self):
        """The old PowerShell reader returned the first match regardless of
        nesting, so every profile resolved to planning's numbers."""
        data = parse(
            "profiles:\n"
            "  planning:\n"
            "    max_turns: 20\n"
            "    effort: medium\n"
            "  implementing:\n"
            "    max_turns: 50\n"
            "    effort: high\n"
        )
        self.assertEqual(data["profiles"]["planning"]["max_turns"], 20)
        self.assertEqual(data["profiles"]["implementing"]["max_turns"], 50)
        self.assertEqual(data["profiles"]["implementing"]["effort"], "high")


class TestLists(unittest.TestCase):
    def test_block_list_indented(self):
        data = parse("deny:\n  - Read(./.env)\n  - Edit(./.git/**)\n")
        self.assertEqual(data["deny"], ["Read(./.env)", "Edit(./.git/**)"])

    def test_block_list_flush(self):
        data = parse("deny:\n- a\n- b\n")
        self.assertEqual(data["deny"], ["a", "b"])

    def test_inline_list(self):
        self.assertEqual(parse("items: [a, b, c]")["items"], ["a", "b", "c"])
        self.assertEqual(parse("nums: [1, 2]")["nums"], [1, 2])
        self.assertEqual(parse("empty: []")["empty"], [])

    def test_list_of_mappings(self):
        data = parse(
            "checks:\n"
            "  - name: unit\n"
            "    command: pytest\n"
            "  - name: lint\n"
            "    command: ruff check\n"
        )
        self.assertEqual(
            data["checks"],
            [
                {"name": "unit", "command": "pytest"},
                {"name": "lint", "command": "ruff check"},
            ],
        )

    def test_list_after_mapping_key_then_sibling(self):
        data = parse("deny:\n  - a\nother: 1\n")
        self.assertEqual(data["deny"], ["a"])
        self.assertEqual(data["other"], 1)


class TestUnsupported(unittest.TestCase):
    """Unsupported syntax must raise, never silently misparse."""

    def test_tabs_rejected(self):
        with self.assertRaises(YamlError):
            parse("a:\n\tb: 1\n")

    def test_flow_mapping_rejected(self):
        with self.assertRaises(YamlError):
            parse("a: {b: 1}")

    def test_block_scalar_rejected(self):
        with self.assertRaises(YamlError):
            parse("a: |\n  text\n")

    def test_anchor_rejected(self):
        with self.assertRaises(YamlError):
            parse("a: &anchor 1")

    def test_multi_document_rejected(self):
        with self.assertRaises(YamlError):
            parse("---\na: 1\n")

    def test_missing_colon_rejected(self):
        with self.assertRaises(YamlError):
            parse("just some text\n")

    def test_top_level_list_rejected(self):
        with self.assertRaises(YamlError):
            parse("- a\n- b\n")


if __name__ == "__main__":
    unittest.main()
