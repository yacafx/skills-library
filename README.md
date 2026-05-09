# Skills Library

A practical, portable library of reusable Agent Skills.

## Purpose

This repository stores skills in a versioned, shareable format so they can be reused across coding agents and tools.

## Skill layout

Each skill lives in its own folder under `skills/`:

```text
skills/
  <skill-name>/
    SKILL.md
    references/   # optional
    scripts/      # optional
    assets/       # optional
```

## Installation pattern

Use the same skill folder and place it in your tool's skills directory.

- Cursor/Codex/Claude Code: install to the tool's user-level or project-level skills path.
- For other clients: follow vendor docs and point to this same folder structure.

References:
- [Agent Skills specification](https://agentskills.io/specification)
- [Agent Skills client showcase](https://agentskills.io/clients)

## Usage pattern

Keep invocation explicit when needed (for example, `decompose: ...`) and describe trigger behavior clearly in each skill's `SKILL.md`.

## Repository roadmap

- Add one skill per folder under `skills/`.
- Keep `SKILL.md` portable and standards-first.
- Put product-specific installation notes in this README, not inside each skill implementation unless necessary.
