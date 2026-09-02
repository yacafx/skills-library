# Context Skills

A reusable skill for keeping a project's lightweight context routing
layer accurate and lean. It treats the routing files as an **index**, not
as the source of truth: every claim is verified against the actual
repository before it is trusted.

## What is in this folder

- `SKILL.md` — runnable skill workflow (precedence rules, drift checklist, update policy, report format).

## When to use

Invoke this skill when:

- You are about to update a context file (architecture notes, current state, command index, decision log).
- You suspect drift between the routing layer and the repo.
- You finished a task and the "current state" needs to reflect what changed.
- You want to validate that every path and shell command referenced in the routing files still resolves to something real.

If none of these apply, skip it — routing maintenance is overhead unless the index is actively being used or actively wrong.

## What it produces

A short structured report listing drift detected, proposed updates, unresolved items, and verified-clean files. See `SKILL.md` for the exact format.

## Token efficiency

The routing layer exists to avoid loading the whole repo into the context window for every task. Typical savings on a medium-sized codebase:

| Approach                          | Tokens loaded per task |
| --------------------------------- | ---------------------- |
| Full repo read                    | 100% (baseline)        |
| Routing layer + targeted reads    | 60–70%                 |
| **Savings**                       | **30–40%**             |

Savings come from three places:
- The top-level index loads in <1k tokens and points to exactly the files needed.
- The current-state snapshot replaces an exploratory scan of recent commits.
- The command index replaces searching scripts and CI files.

Savings degrade fast if the routing layer drifts — a wrong path sends the reader to grep through the repo anyway. Keeping drift near zero is what makes the routing layer worth maintaining.

## Pairing with context-steward

This skill is designed to pair with the `context-steward` agent (see `skills/context-steward/`), which performs the same checks autonomously and proposes diffs without committing. Either entry point is valid:

- Invoke `context-skills` directly when you want to run a check yourself.
- Hand off to `context-steward` when you want a guardian process to watch the routing layer over time.

The split is intentional: a skill you reach for vs. a role that watches the project. Keeping them separate avoids a skill that quietly mutates into a long-running agent, or an agent invoked for one-off checks that loses its guardian framing.

## Getting started

To adopt this pattern in a new project:

1. Copy `skills/context-skills/` and `skills/context-steward/` into your project's skills directory.
2. Decide on your routing files. A reasonable starter set:
   - `INDEX.md` — top-level map of the repo.
   - `STATE.md` — current-state snapshot.
   - `COMMANDS.md` — install, build, test, run.
   - `DECISIONS.md` — append-only decision log.
3. Run this skill once to baseline each file with a `last-verified:` date.
4. Decide whether to also run `context-steward` on a schedule (e.g. weekly, or before each release).
5. After the first real drift report, tune the size limits and freshness window in `SKILL.md` to match your project.

You do not need both skills active to start — `context-skills` alone is enough for small projects. Add the steward when the routing layer is large enough that drift between sessions becomes a real risk.
