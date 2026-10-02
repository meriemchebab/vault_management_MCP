# Obsidian MCP Assistant

A local Model Context Protocol (MCP) server turns an Obsidian vault into an interactive second brain for AI coding assistants (Claude Desktop, OpenCode, VS Code, Cursor), allowing models to read notes, search ideas and unfinished tasks, brainstorm with you and put that into a plan in an .md file, record work logs, and synthesize summaries of project progress.



---

## Features

- **Brainstorm & Link:** Create idea notes in `Ideas/` pre-configured with YAML frontmatter and `[[wikilinks]]`.
- **Surgical Edits:** Append items directly under specific Markdown headings (e.g., `## Tasks`) without clobbering neighboring sections.
- **Automated Devlogs:** Log timestamped work sessions, resolved tasks, and blockers into `Projects/<project>.md`.
- **Snippet Library:** Capture code or TILs into `Snippets/` with valid YAML frontmatter, normalized tags, and a syntax-highlighted fenced block.
- **Task & Search Scanning:** Instantly retrieve open checklist items (`- [ ]`) or search keywords across the vault.
- **Weekly Standup Synthesis:** Built-in tool and MCP prompt template to aggregate logs from the past $N$ days for executive sprint recaps.


---


## Requirements

- Python 3.13 or later
- [`uv`](https://docs.astral.sh/uv/) for environment and dependency management
- Obsidian vault at the configured path above

The project dependency is `mcp[cli]` 2.2.0 or later.

## Setup

From the project directory, sync the dependencies and start the server over stdio:

```powershell
uv sync
uv run main.py
```

To use a different vault, change `VAULT_DIR` near the top of `main.py`. On Windows, use a raw string, for example:

```python
VAULT_DIR = Path(r"C:\Users\your-name\Documents\Obsidian Vault")
```

## MCP client configuration

Configure your MCP client to launch this project's `main.py` using `uv`. For example, in a client configuration that supports an `mcpServers` object:

```json
{
  "mcpServers": {
    "obsidian-project-manager": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Users\\hp\\OneDrive\\Documents\\volt_management_MCP",
        "run",
        "main.py"
      ]
    }
  }
}
```

Replace the project directory if you cloned or moved the repository elsewhere. The `obsidian-project-manager` key is the client-side server name; the server itself uses stdio transport.

## Tools

| Tool | Parameters | What it does |
| --- | --- | --- |
| `list_notes` | None | Lists Markdown filenames in the vault. |
| `read_note` | `note_name: str` | Reads a note by its filename or title, with or without `.md`. |
| `search_vault` | `keyword: str` | Searches note contents and returns up to 15 matches. |
| `append_to_daily_note` | `entry: str` | Adds a bullet to today's `YYYY-MM-DD.md` note, creating it if needed. |
| `list_open_tasks` | None | Finds up to 30 unchecked Markdown tasks (`- [ ]`). |
| `append_under_heading` | `note_name: str, heading: str, content: str` | Adds content under a heading, creating that heading if absent. |
| `create_idea_note` | `title: str, summary: str, body: str, tags: list[str], related_notes: list[str] = []` | Creates a structured note under `Ideas/`. |
| `log_dev_session` | `project_name: str, summary: str, completed_tasks: list[str], blockers_or_next_steps: str = ""` | Records a timestamped session in `Projects/<project_name>.md`. |
| `get_recent_devlogs` | `days: int = 7` | Collects project sessions from the previous number of days. |
| `save_code_snippet` | `title: str, language: str, code: str, explanation: str, tags: list[str] = [], source_project: str = ""` | Saves a code snippet or TIL note under `Snippets/` with YAML frontmatter, kebab-case tags, and a fenced code block. |

## Prompt

`weekly_standup_report(days: int = 7, audience: str = "technical lead")` gathers recent development logs and prepares instructions for an executive weekly standup report, including progress, blockers, and next priorities.
