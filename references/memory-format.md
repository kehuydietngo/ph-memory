# Memory contract v1

`.ph-memory/state.json` is UTF-8 JSON. It contains:

- `schema_version`: 1; `project_id`: UUID (retained on transfer); `revision`: integer, incremented by CLI.
- `name`, `purpose`, `current_task`: strings; `updated_at`: UTC ISO timestamp maintained by CLI.
- `facts`, `decisions`, `completed`, `issues`: lists of objects with nonempty `claim`, one of the four statuses in SKILL.md, and nonempty `evidence`. Unknown details belong in issues as unverified, with a reference to the observation that exposed the gap.
- `next_actions`: ordered list of strings, each a concrete action.
- `assets`: list of `{path, role, sha256, size}`; relative paths stay within the project. Use `asset` to register. Never put a media binary in JSON.
- `video`: object; optional fields described in video.md. Keep it concise; use evidence paths for large timelines.

Use `state --root PATH` to print editable JSON. A checkpoint must preserve project_id and revision and use the exact supported top-level fields. The CLI rejects malformed records and oversized state (128 KiB). Its resume packet prioritizes current task and next actions, then constraints and completed work, with a visible truncation notice. Increase `--max-chars` or read targeted state sections if a constraint is omitted. Characters are deterministic; token counts vary by model and language.

History: the CLI keeps the last 10 prior snapshots locally under `.ph-memory/history`. History is not exported. Full creative history belongs in deliberate topic notes, never an accumulating conversation dump. Asset registration also advances the revision; reread state before the next checkpoint.

Concurrency: all CLI writes to state/derived resume use `.ph-memory/.lock`. A CLI conflict must be reconciled semantically. Do not manually edit live state while another agent writes. PROJECT_MEMORY.md edits are outside that lock; coordinate them when sharing a checkout. Work on separate branches/worktrees still requires explicit reconciliation before merging.

Privacy: state and resume may contain private client plans. Initialization adds `/.ph-memory/` to project .gitignore; already-tracked files are not untracked. Review Git's staged files before publishing. PROJECT_MEMORY.md is not automatically ignored because projects may intentionally track a sanitized summary; never put secrets or private client material there. Export scans common credential shapes but cannot recognize all secrets or personal information. No network calls occur in the CLI.
