# Context Steward

A guardian agent for the project's lightweight context routing system.
Its job is to watch the routing layer over time, detect drift, and
propose corrections — never to commit them. A human or higher-authority
agent always reviews and applies the steward's proposals.

## What is in this folder

- `SKILL.md` — agent definition (role, inputs, checks, severity levels, allowed/forbidden changes, output format).

## When to use

Activate the steward when:

- The project has a routing layer large enough that drift between contributor sessions becomes a real risk.
- You want a periodic audit (weekly, before a release) rather than an on-demand check.
- A human reviewer is available to apply the steward's proposed diffs.

If you only need a one-off maintenance pass, use the `context-skills` skill directly instead — the steward role implies an ongoing watch.

## What it produces

A single structured report per run:

- Findings classified by severity (HIGH / MED / LOW), each with evidence and a one-line proposal.
- Unresolved items the steward could not verify.
- Files verified clean.
- A diff bundle, attached or inline.

The report is the steward's only deliverable. Anything not in the report did not happen.

## Severity levels

- **HIGH** — broken paths, failing commands, "current state" contradicting HEAD, links to deleted files.
- **MEDIUM** — stale freshness window with new commits in the area, command output changed, two routing files disagreeing, active decisions whose implementation was removed.
- **LOW** — soft size target exceeded, inconsistent format, less-canonical link target, stale wording.

## Operating principles

- **Evidence or silence.** Every finding cites a path, a command, or a commit.
- **Repository wins.** When the routing layer and the repo disagree, the repo is correct by definition.
- **Smallest correct change.** Prefer a one-line fix to a rewrite. Prefer a rewrite to a deletion. Prefer a deletion to silent rot.
- **No autonomous commits.** Even if the fix is obvious. The human reviewer is part of the contract.
- **Re-verify.** Trust no prior run, including the steward's own.

## Pairing with context-skills

The steward shares its precedence rules and drift-detection checklist with the `context-skills` skill (see `skills/context-skills/`). The difference is operational:

- `context-skills` is a tool a contributor reaches for during a session.
- `context-steward` is a standing role that audits between sessions and surfaces drift.

Keeping them separate avoids two failure modes: a skill mutating into a long-running agent, or an agent losing its guardian framing because it gets invoked for one-off checks.
