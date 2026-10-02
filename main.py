import re
from datetime import date, datetime, timedelta
from pathlib import Path
from mcp.server.mcpserver import MCPServer



# update this to absolute Obsidian vault path

VAULT_DIR = Path(r"C:\\Users\hp\\Documents\Obsidian Vault").resolve()

mcp = MCPServer("obsidian-project-manager")


# helper function for search
def _find_target_file(note_name: str) -> Path | None:
    """Finds a note by name (case-insensitive, with or without .md extension)."""
    clean_name = note_name[:-3] if note_name.lower().endswith(".md") else note_name
    for path in VAULT_DIR.rglob("*.md"):
        if path.stem.lower() == clean_name.lower():
            return path
    return None


@mcp.tool()
def list_notes() -> list[str]:
    """List all markdown note filenames currently in the Obsidian vault."""
    if not VAULT_DIR.exists():
        return [f"ERROR: Vault directory not found at: {VAULT_DIR}"]
    
    files = [p.name for p in VAULT_DIR.rglob("*") if p.suffix.lower() == ".md"]
    if not files:
        return [f"DEBUG: Vault path exists at {VAULT_DIR}, but 0 .md files were matched."]
    return sorted(files)



@mcp.tool()
def read_note(note_name: str) -> str:
    """Read the full text content of a specific markdown note."""
    file_path = _find_target_file(note_name)
    if not file_path:
        return f"Error: Note '{note_name}' was not found in the vault."
    return file_path.read_text(encoding="utf-8", errors="ignore")


@mcp.tool()
def search_vault(keyword: str) -> list[dict]:
    """Search for notes containing a specific keyword or tag across the entire vault."""
    matches = []
    for file_path in VAULT_DIR.rglob("*.md"):
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        if keyword.lower() in content.lower():
            matches.append({
                "file": file_path.stem,
                "relative_path": str(file_path.relative_to(VAULT_DIR))
            })
    return matches[:15]

@mcp.tool()
def append_to_daily_note(entry: str) -> str:
    """Appends a new thought, log, or task to today's daily note (YYYY-MM-DD.md)."""
    today_str = date.today().isoformat()
    daily_file = VAULT_DIR / f"{today_str}.md"
    
    prefix = "" if daily_file.exists() and daily_file.stat().st_size > 0 else f"# {today_str}\n\n"
    with open(daily_file, "a", encoding="utf-8") as f:
        f.write(f"{prefix}- {entry}\n")
        
    return f"Successfully added entry to {today_str}.md"


@mcp.tool()
def list_open_tasks() -> list[str]:
    """Finds all uncompleted tasks ('- [ ]') across all markdown notes in the vault."""
    open_tasks = []
    for file_path in VAULT_DIR.rglob("*.md"):
        for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("- [ ]"):
                open_tasks.append(f"{file_path.stem}: {line.strip()}")
    return open_tasks[:30]


@mcp.tool()
def append_under_heading(note_name: str, heading: str, content: str) -> str:
    """
    Appends text directly under a specific Markdown heading inside a note.
    
    Args:
        note_name: The title or filename of the note (e.g. 'Project Tracker' or '2026-09-29').
        heading: The heading title with or without markdown symbols (e.g. '## Tasks' or 'Tasks').
        content: The text to insert ('e.g. - [ ] Review vector embeddings').
    """
    file_path = _find_target_file(note_name)
    if not file_path:
        return f"Error: Note '{note_name}' was not found in the vault."

    raw_heading = heading.strip()
    match = re.match(r"^(#+)\s*(.*)$", raw_heading)
    if match:
        heading_level = len(match.group(1))
        heading_title = match.group(2).strip()
    else:
        heading_level = 2
        heading_title = raw_heading

    heading_pattern = re.compile(
        rf"^{re.escape('#' * heading_level)}\s+{re.escape(heading_title)}\s*$",
        re.IGNORECASE
    )

    lines = file_path.read_text(encoding="utf-8").splitlines()
    target_idx = None

    for idx, line in enumerate(lines):
        if heading_pattern.match(line.strip()):
            target_idx = idx
            break

    if target_idx is not None:
        insert_idx = len(lines)
        for idx in range(target_idx + 1, len(lines)):
            line = lines[idx].strip()
            boundary_match = re.match(r"^(#+)\s+.*", line)
            if boundary_match:
                insert_idx = idx
                break

        while insert_idx > target_idx + 1 and lines[insert_idx - 1].strip() == "":
            insert_idx -= 1

        lines.insert(insert_idx, content)
        status = f"Appended under '{'#' * heading_level} {heading_title}' in {file_path.name}"
    else:
        lines.append("")
        lines.append(f"{'#' * heading_level} {heading_title}")
        lines.append(content)
        status = f"Created '{'#' * heading_level} {heading_title}' and appended content in {file_path.name}"

    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return status


@mcp.tool()
def create_idea_note(
    title: str,
    summary: str,
    body: str,
    tags: list[str],
    related_notes: list[str] = []
) -> str:
    """
    Creates an atomic idea note formatted with YAML frontmatter and Obsidian wikilinks.
    places notes into an 'Ideas' directory within the vault.
    """
    ideas_dir = VAULT_DIR / "Ideas"
    ideas_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = ideas_dir / f"{title.strip().replace('/', '-')}.md"
    today_str = date.today().isoformat()
    
    tags_formatted = "\n".join([f"  - {t.strip('#')}" for t in tags])
    wikilinks = "\n".join([f"- [[{n}]]" for n in related_notes])
    
    content = f"""---
created: {today_str}
type: idea
tags:
{tags_formatted}
---

# {title}

> **Summary:** {summary}

## Concept Details
{body}

## Related Links
{wikilinks if wikilinks else "None"}
"""
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    return f"Created idea note: Ideas/{file_path.name}"



@mcp.tool()
def log_dev_session(
    project_name: str,
    summary: str,
    completed_tasks: list[str],
    blockers_or_next_steps: str = ""
) -> str:
    """
    Appends a timestamped work log to a project's devlog note in Projects/<project_name>.md.
    """
    projects_dir = VAULT_DIR / "Projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = projects_dir / f"{project_name.strip()}.md"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tasks_md = "\n".join([f"  - [x] {task}" for task in completed_tasks])
    blockers_md = f"\n  - **Next Steps / Blockers:** {blockers_or_next_steps}" if blockers_or_next_steps else ""
    
    entry_block = f"""
### Session: {now_str}
- **Overview:** {summary}
- **Accomplishments:**
{tasks_md}{blockers_md}
"""
    if not file_path.exists():
        file_path.write_text("", encoding="utf-8")

    return append_under_heading(
        note_name=file_path.name,
        heading="## Development Log",
        content=entry_block.strip()
    )


@mcp.tool()
def get_recent_devlogs(days: int = 7) -> str:
    """
    Extracts work session entries logged within the past N days across all project files.
    Looks for notes inside the 'Projects/' folder with a '## Development Log' section.
    """
    projects_dir = VAULT_DIR / "Projects"
    if not projects_dir.exists():
        return "No 'Projects' directory found in the vault."

    cutoff_date = datetime.now() - timedelta(days=days)
    devlog_header_re = re.compile(r"^##\s+Development\s+Log\b", re.IGNORECASE)
    session_header_re = re.compile(r"^###\s+Session:\s*(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?)", re.IGNORECASE)
    any_h2_re = re.compile(r"^##\s+")

    recap_by_project = {}

    for file_path in projects_dir.glob("*.md"):
        project_name = file_path.stem
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        
        in_devlog = False
        devlog_lines = []
        for line in lines:
            if devlog_header_re.match(line.strip()):
                in_devlog = True
                continue
            elif in_devlog and any_h2_re.match(line.strip()):
                break
            
            if in_devlog:
                devlog_lines.append(line)

        if not devlog_lines:
            continue

        current_session_dt = None
        current_block = []
        matching_sessions = []

        def flush_session():
            if current_session_dt and current_session_dt >= cutoff_date:
                matching_sessions.append("\n".join(current_block).strip())

        for line in devlog_lines:
            match = session_header_re.match(line.strip())
            if match:
                flush_session()
                date_str = match.group(1).strip()
                try:
                    if len(date_str) > 10:
                        current_session_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                    else:
                        current_session_dt = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    current_session_dt = None

                current_block = [line]
            elif current_session_dt is not None:
                current_block.append(line)

        flush_session()

        if matching_sessions:
            recap_by_project[project_name] = matching_sessions

    if not recap_by_project:
        return f"No devlog sessions found in the last {days} days."

    output = [f"# Aggregated Devlogs (Past {days} Days)\n"]
    for project, sessions in recap_by_project.items():
        output.append(f"## Project: {project}\n")
        output.append("\n\n".join(sessions))
        output.append("\n---\n")

    return "\n".join(output).strip()


# Prompt Template: executive Weekly Standup

@mcp.prompt()
def weekly_standup_report(days: int = 7, audience: str = "technical lead") -> str:
    """
    Generates a structured executive weekly standup and sprint summary
    based on the development logs from the past N days.
    """
    raw_logs = get_recent_devlogs(days=days)

    return f"""
You are an experienced technical project manager and software engineering lead.
Here are the raw work sessions and development logs recorded across all active projects over the last {days} days:

<devlogs>
{raw_logs}
</devlogs>

synthesize these raw session entries into an **Executive Weekly Standup Report** tailored for a {audience}.

### Required Structure:
1. **Executive Highlights**: A 2-3 sentence overview of major momentum, critical milestones achieved, and focus areas this week.
2. **Project-by-Project Progress**:
   - For each active project:
     - **Shipped / Accomplished**: Key tasks closed or features completed.
     - **In Flight / Pending**: Work currently in progress.
3. **Blockers & Risk Analysis**:
   - Technical hurdles, external dependencies, or unaddressed bugs mentioned in logs.
4. **Immediate Priorities (Next Sprint / Week)**:
   - 3-5 high-impact, actionable items to tackle next based on recorded next steps.

Guidelines:
- Strip away raw timestamps and conversational filler.
- Keep the language crisp, outcome-driven, and focused on value delivered.
"""

def _sanitize_filename(name: str) -> str:
    """Removes characters illegal in Windows/macOS/Linux filenames and Obsidian titles."""
    # Strip illegal Windows characters: \ / : * ? " < > |
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    # Replace whitespace sequences with a single space
    sanitized = re.sub(r"\s+", " ", sanitized)
    return sanitized or "Untitled Snippet"


def _sanitize_tag(name: str) -> str:
    """Normalizes a string into a safe Obsidian/YAML tag (lowercase kebab-case)."""
    slug = re.sub(r"[^a-zA-Z0-9_\-\/]+", "-", name.strip().lstrip("#").lower())
    return slug.strip("-")


@mcp.tool()
def save_code_snippet(
    title: str,
    language: str,
    code: str,
    explanation: str,
    tags: list[str] | None = None,
    source_project: str | None = ""
) -> str:
    """
    Saves a code snippet or TIL (Today I Learned) note into the 'Snippets/' folder
    with clean Obsidian frontmatter, tags, and fenced code.

    Args:
        title: Short descriptive name (e.g., 'Savitzky-Golay Signal Smoothing').
        language: Programming or config language for syntax highlighting (e.g. 'python', 'cpp', 'bash', 'json').
        code: The raw code snippet to preserve.
        explanation: Clear explanation of what problem this solves and how it works.
        tags: List of keywords/tags without the '#' prefix (e.g. ['python', 'dsp', 'algorithms']).
        source_project: (Optional) Name of the project or context where this was solved (e.g. 'Chrono-Forest').
    """
    try:
        title = "" if title is None else str(title)
        language = "" if language is None else str(language)
        code = "" if code is None else str(code)
        explanation = "" if explanation is None else str(explanation)

        tag_values = [] if tags is None else list(tags)
        if isinstance(tags, str):
            tag_values = [tags]

        source_project_value = "" if source_project is None else str(source_project).strip()

        snippets_dir = VAULT_DIR / "Snippets"
        snippets_dir.mkdir(parents=True, exist_ok=True)

        clean_title = _sanitize_filename(title)
        file_path = snippets_dir / f"{clean_title}.md"

        today_str = date.today().isoformat()
        clean_lang = language.strip().lower()

        # Build clean tags list (ensure 'snippet' is always included)
        tag_set = {"snippet"}
        for t in tag_values:
            # Normalize multi-word tags to kebab-case: "Retry Logic" -> "retry-logic"
            slug = _sanitize_tag(str(t))
            if slug:
                tag_set.add(slug)
        if clean_lang:
            tag_set.add(_sanitize_tag(clean_lang))

        tags_yaml = "\n".join([f"  - {t}" for t in sorted(tag_set)])

        # Optional wikilink to parent project
        project_link = f"- [[{source_project_value}]]" if source_project_value else "None"

        frontmatter = "\n".join(
            [
                
                f"created: {today_str}",
                "type: snippet",
                f"language: {clean_lang}",
                "tags:",
                tags_yaml,
                
            ]
        )
        body_lines = [
            f"# {clean_title}",
            "",
            "> **Context & Problem:**",
            f"> {explanation.strip()}",
            "",
            "## Implementation",
            "",
            f"```{clean_lang}",
            code.rstrip("\n"),
            "```",
            "",
            "## References & Projects",
            project_link,
        ]
        content = frontmatter + "\n\n" + "\n".join(body_lines) + "\n"

        file_path.write_text(content.strip() + "\n", encoding="utf-8")
        return f"Successfully saved snippet to: Snippets/{file_path.name}"

    except Exception as e:
        return f"Failed to save code snippet: {str(e)}"

# Server Entrypoint

if __name__ == "__main__":
    mcp.run(transport="stdio")
