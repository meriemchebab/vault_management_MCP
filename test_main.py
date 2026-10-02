"""Pytest behavior tests for the Obsidian MCP server functions."""

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import main


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """Keep all test reads and writes inside an isolated temporary vault."""
    monkeypatch.setattr(main, "VAULT_DIR", tmp_path)
    return tmp_path


def test_find_target_file_is_case_insensitive_and_accepts_extension(vault):
    note = vault / "Folder" / "Project.md"
    note.parent.mkdir()
    note.write_text("hello", encoding="utf-8")

    assert main._find_target_file("project") == note
    assert main._find_target_file("PROJECT.MD") == note
    assert main._find_target_file("missing") is None


def test_list_notes_handles_missing_empty_and_populated_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "VAULT_DIR", tmp_path / "missing")
    assert main.list_notes()[0].startswith("ERROR: Vault directory not found")

    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    monkeypatch.setattr(main, "VAULT_DIR", vault_path)
    assert main.list_notes()[0].startswith("DEBUG: Vault path exists")

    (vault_path / "z.md").write_text("z", encoding="utf-8")
    (vault_path / "nested").mkdir()
    (vault_path / "nested" / "a.MD").write_text("a", encoding="utf-8")
    assert main.list_notes() == ["a.MD", "z.md"]


def test_read_note_returns_content_and_missing_message(vault):
    (vault / "Note.md").write_text("note body", encoding="utf-8")
    assert main.read_note("note") == "note body"
    assert "was not found" in main.read_note("unknown")


def test_search_vault_finds_case_insensitive_matches_and_caps_results(vault):
    (vault / "Alpha.md").write_text("A Secret phrase", encoding="utf-8")
    (vault / "sub").mkdir()
    (vault / "sub" / "Beta.md").write_text("secret PHRASE", encoding="utf-8")

    results = main.search_vault("SECRET")
    assert [item["file"] for item in results] == ["Alpha", "Beta"]
    assert results[0]["relative_path"] == "Alpha.md"
    assert results[1]["relative_path"].endswith("Beta.md")

    for index in range(16):
        (vault / f"match-{index}.md").write_text("needle", encoding="utf-8")
    assert len(main.search_vault("needle")) == 15


def test_append_to_daily_note_creates_then_appends(vault, monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 30)

    monkeypatch.setattr(main, "date", FixedDate)
    assert main.append_to_daily_note("first entry") == "Successfully added entry to 2026-09-30.md"
    assert (vault / "2026-09-30.md").read_text(encoding="utf-8") == (
        "# 2026-09-30\n\n- first entry\n"
    )
    main.append_to_daily_note("second entry")
    assert (vault / "2026-09-30.md").read_text(encoding="utf-8").endswith(
        "- first entry\n- second entry\n"
    )


def test_list_open_tasks_finds_unchecked_tasks_and_caps_results(vault):
    (vault / "Work.md").write_text(
        "- [ ] do this\n- [x] done\n  - [ ] nested\n", encoding="utf-8"
    )
    assert main.list_open_tasks() == ["Work: - [ ] do this", "Work: - [ ] nested"]

    for index in range(31):
        (vault / f"task-{index}.md").write_text("- [ ] task\n", encoding="utf-8")
    assert len(main.list_open_tasks()) == 30


def test_append_under_heading_inserts_before_next_peer_heading(vault):
    note = vault / "Plan.md"
    note.write_text(
        "# Plan\n## Tasks\n- existing\n\n### Detail\nkeep\n\n## Later\nleave\n",
        encoding="utf-8",
    )
    result = main.append_under_heading("Plan", "Tasks", "- added")
    content = note.read_text(encoding="utf-8")
    assert "Appended under '## Tasks'" in result
    assert content.index("- added") < content.index("### Detail")
    assert content.index("### Detail") < content.index("## Later")


def test_append_under_heading_creates_missing_heading_and_reports_missing_note(vault):
    note = vault / "Plan.md"
    note.write_text("# Plan\n", encoding="utf-8")
    result = main.append_under_heading("Plan.md", "### Risks", "- blocked")
    assert "Created '### Risks'" in result
    assert "### Risks\n- blocked" in note.read_text(encoding="utf-8")
    assert "was not found" in main.append_under_heading("missing", "Tasks", "x")


def test_create_idea_note_writes_frontmatter_tags_and_links(vault):
    result = main.create_idea_note(
        "Useful Idea", "Short summary", "Long explanation", ["#ai", "planning"], ["Project A"]
    )
    content = (vault / "Ideas" / "Useful Idea.md").read_text(encoding="utf-8")
    assert result == "Created idea note: Ideas/Useful Idea.md"
    assert "type: idea" in content
    assert "  - ai" in content
    assert "  - planning" in content
    assert "> **Summary:** Short summary" in content
    assert "- [[Project A]]" in content


def test_log_dev_session_creates_project_note_and_adds_session(vault, monkeypatch):
    fixed_now = datetime(2026, 9, 30, 12, 34)

    class FixedDateTime:
        @classmethod
        def now(cls):
            return fixed_now

    monkeypatch.setattr(main, "datetime", FixedDateTime)
    result = main.log_dev_session("Widget", "Built a feature", ["added endpoint"], "Review tests")
    project_files = list((vault / "Projects").glob("*.md"))
    assert len(project_files) == 1
    content = project_files[0].read_text(encoding="utf-8")
    assert "Created '## Development Log'" in result
    assert "### Session: 2026-09-30 12:34" in content
    assert "- **Overview:** Built a feature" in content
    assert "- [x] added endpoint" in content
    assert "**Next Steps / Blockers:** Review tests" in content


def test_get_recent_devlogs_filters_by_cutoff_and_handles_no_projects(vault):
    assert main.get_recent_devlogs() == "No 'Projects' directory found in the vault."
    projects = vault / "Projects"
    projects.mkdir()
    recent = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    old = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d %H:%M")
    (projects / "Widget.md").write_text(
        f"## Development Log\n### Session: {recent}\n- recent work\n"
        f"### Session: {old}\n- old work\n\n## Other\nignore\n",
        encoding="utf-8",
    )

    result = main.get_recent_devlogs(days=7)
    assert "Project: Widget" in result
    assert "recent work" in result
    assert "old work" not in result
    assert "ignore" not in result
    assert "No devlog sessions found" in main.get_recent_devlogs(days=0)


def test_weekly_standup_prompt_includes_logs_days_and_audience(monkeypatch):
    monkeypatch.setattr(
        main, "get_recent_devlogs", lambda days: f"sample logs for {days} days"
    )
    prompt = main.weekly_standup_report(days=5, audience="engineering director")
    assert "sample logs for 5 days" in prompt
    assert "engineering director" in prompt
    assert "Blockers & Risk Analysis" in prompt


# ---------------------------------------------------------------------------
# save_code_snippet
# ---------------------------------------------------------------------------


@pytest.fixture
def fixed_today(monkeypatch):
    """Pin date.today() so the 'created:' frontmatter is deterministic."""

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 2)

    monkeypatch.setattr(main, "date", FixedDate)


def _frontmatter(content: str) -> list[str]:
    """Return the raw lines between the opening '---' and the closing '---'."""
    lines = content.splitlines()
    assert lines[0] == "---", "frontmatter must open on the very first line"
    end = lines.index("---", 1)
    return lines[1:end]


def test_save_code_snippet_creates_snippets_folder_and_returns_path(vault):
    result = main.save_code_snippet("My Snippet", "python", "print(1)", "why")

    assert result == "Successfully saved snippet to: Snippets/My Snippet.md"
    assert (vault / "Snippets" / "My Snippet.md").is_file()


def test_save_code_snippet_frontmatter_is_unindented_and_parses(vault, fixed_today):
    """Regression: frontmatter keys used to be indented 8 spaces, which made
    the block invalid YAML because injected tag lines were only indented 2."""
    main.save_code_snippet(
        "FM", "python", "print(1)", "why", tags=["python", "retry logic"]
    )
    content = (vault / "Snippets" / "FM.md").read_text(encoding="utf-8")
    fm_lines = _frontmatter(content)

    # 'tags:' owns its indented sequence items; the keys themselves must sit at
    # column 0. Mixing the two indent levels is what made the block invalid.
    key_lines = [line for line in fm_lines if not line.startswith("  ")]
    assert [line.split(":")[0] for line in key_lines] == [
        "created",
        "type",
        "language",
        "tags",
    ]
    for line in key_lines:
        assert line == line.lstrip(), f"frontmatter key must not be indented: {line!r}"
    assert "created: 2026-10-02" in fm_lines
    assert "type: snippet" in fm_lines

    # Every tag entry shares one identical indent level.
    tag_lines = [line for line in fm_lines if line.startswith(" ")]
    assert tag_lines, "expected at least one tag"
    indents = {len(line) - len(line.lstrip()) for line in tag_lines}
    assert indents == {2}


def test_save_code_snippet_closes_the_code_fence(vault):
    """Regression: the fence was never closed, so '## References' was rendered
    as part of the code block."""
    main.save_code_snippet(
        "Fence", "python", "print(1)", "why", source_project="Proj"
    )
    content = (vault / "Snippets" / "Fence.md").read_text(encoding="utf-8")

    assert content.count("```") == 2, "exactly one open and one close fence"
    close_idx = content.index("```", content.index("```") + 3)
    references_idx = content.index("## References & Projects")
    assert close_idx < references_idx, "fence must close before the References heading"


def test_save_code_snippet_preserves_code_indentation(vault):
    """Regression: the first code line used to pick up the template's own
    indentation, leaving it misaligned with the rest of the snippet."""
    code = "def f():\n    if True:\n        return 1\n"
    main.save_code_snippet("Indent", "python", code, "why")

    content = (vault / "Snippets" / "Indent.md").read_text(encoding="utf-8")
    body = content.split("```python\n", 1)[1].split("\n```", 1)[0]

    assert body.splitlines() == [
        "def f():",
        "    if True:",
        "        return 1",
    ]


def test_save_code_snippet_normalizes_and_dedupes_tags(vault):
    main.save_code_snippet(
        "Tags",
        "  PYTHON  ",
        "print(1)",
        "why",
        tags=["#Retry Logic", "resilience", "retry logic", "  ", "c++", "!!!"],
    )
    content = (vault / "Snippets" / "Tags.md").read_text(encoding="utf-8")

    assert "  - retry-logic" in content
    assert "  - resilience" in content
    assert "  - snippet" in content
    assert "  - python" in content
    assert "  - c" in content
    assert content.count("  - retry-logic") == 1, "tags must be de-duplicated"
    # Nothing that would break the YAML or Obsidian's tag rules.
    assert "retrylogic" not in content
    assert "!!!" not in content


def test_save_code_snippet_omits_project_line_when_not_provided(vault):
    main.save_code_snippet("NoProj", "python", "print(1)", "why")
    content = (vault / "Snippets" / "NoProj.md").read_text(encoding="utf-8")

    assert "- [[]]" not in content
    assert content.rstrip().endswith("None")


def test_save_code_snippet_sanitizes_title_for_illegal_filename_chars(vault):
    """Illegal characters are deleted outright, so 'Deep/Dive' becomes 'DeepDive'."""
    result = main.save_code_snippet(
        'Deep/Dive: "v2"? <now> |x|', "python", "print(1)", "why"
    )

    assert result == "Successfully saved snippet to: Snippets/DeepDive v2 now x.md"
    assert (vault / "Snippets" / "DeepDive v2 now x.md").is_file()


def test_save_code_snippet_collapses_whitespace_in_title(vault):
    result = main.save_code_snippet("Lots   of\tspace", "python", "print(1)", "why")

    assert result == "Successfully saved snippet to: Snippets/Lots of space.md"


def test_save_code_snippet_falls_back_to_untitled_for_blank_title(vault):
    result = main.save_code_snippet("   ", "python", "print(1)", "why")

    assert result == "Successfully saved snippet to: Snippets/Untitled Snippet.md"


def test_save_code_snippet_overwrites_existing_note_of_same_title(vault):
    main.save_code_snippet("Dup", "python", "print(1)", "first")
    main.save_code_snippet("Dup", "python", "print(2)", "second")

    files = list((vault / "Snippets").glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "print(2)" in content
    assert "print(1)" not in content
    assert "second" in content


def test_save_code_snippet_reports_failure_instead_of_raising(vault, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(main.Path, "write_text", boom)
    result = main.save_code_snippet("Boom", "python", "print(1)", "why")

    assert result == "Failed to save code snippet: disk full"


def test_save_code_snippet_handles_empty_code_and_explanation(vault):
    result = main.save_code_snippet("Empty", "python", "", "")
    content = (vault / "Snippets" / "Empty.md").read_text(encoding="utf-8")

    assert result == "Successfully saved snippet to: Snippets/Empty.md"
    assert content.count("```") == 2


def test_save_code_snippet_accepts_none_for_optional_fields(vault):
    result = main.save_code_snippet(
        "OptionalFields",
        "python",
        "print(1)",
        None,
        tags=None,
        source_project=None,
    )
    content = (vault / "Snippets" / "OptionalFields.md").read_text(encoding="utf-8")

    assert result == "Successfully saved snippet to: Snippets/OptionalFields.md"
    assert "  - snippet" in content
    assert content.rstrip().endswith("None")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Retry Logic", "retry-logic"),
        ("#dsp", "dsp"),
        ("  C++  ", "c"),
        ("a//b", "a//b"),
        ("!!!", ""),
        ("", ""),
    ],
)
def test_sanitize_tag(raw, expected):
    assert main._sanitize_tag(raw) == expected

