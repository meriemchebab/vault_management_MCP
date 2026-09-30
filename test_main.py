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
