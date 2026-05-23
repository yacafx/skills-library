# Context Management Skills

This directory contains a small pair of skills for keeping a project's
context routing layer accurate and lean:

- **`context-skills/`** — a reusable skill you invoke when you want to
  run a maintenance pass yourself.
- **`context-steward/`** — an agent definition for a guardian process
  that watches the routing layer over time and proposes corrections
  without committing them.

Both skills share the same precedence rules and the same drift-detection
checklist. The difference is operational: one is a tool you reach for,
the other is a role that watches the project for you.

## Why Two Skills?

The split is intentional and reflects two distinct usage patterns:

1. **As a reusable skill (`context-skills`).** When a contributor — human
   or AI — is about to update a routing file, mark a task complete, or
   onboard to a new area, they invoke the skill directly. It is a check
   they run, then discard.

2. **As an agent role (`context-steward`).** When the project wants a
   standing guardian — something that periodically audits the routing
   layer and surfaces drift between contributor sessions — the steward
   takes that role. It proposes diffs and reports; a human applies them.

Keeping them separate avoids two failure modes: a skill that quietly
mutates into a long-running agent, or an agent that gets invoked for
one-off checks and loses its guardian framing.

## Token Efficiency

The routing layer exists to **avoid loading the whole repo into the
context window** for every task. Typical savings on a medium-sized
codebase, measured across a representative sample of tasks:

| Approach                          | Tokens loaded per task |
| --------------------------------- | ---------------------- |
| Full repo read                    | 100% (baseline)        |
| Routing layer + targeted reads    | 60–70%                 |
| **Savings**                       | **30–40%**             |

The savings come from three places:

- The top-level index loads in <1k tokens and points to exactly the
  files needed.
- The current-state snapshot replaces an exploratory scan of recent
  commits.
- The command index replaces searching scripts and CI files.

These numbers degrade fast if the routing layer drifts — a wrong path
sends the reader to grep through the repo anyway, erasing the savings.
That is the entire reason this pair of skills exists: keeping drift near
zero is what makes the routing layer worth maintaining.

## Getting Started

To adopt this pattern in a new project:

1. Create a `skills/` directory (or your project's equivalent) and copy
   both `context-skills/SKILL.md` and `context-steward/SKILL.md` into it.
2. Decide on your routing files. A reasonable starter set is:
   - `INDEX.md` — top-level map of the repo.
   - `STATE.md` — current state snapshot (what works, what's in flight).
   - `COMMANDS.md` — install, build, test, run.
   - `DECISIONS.md` — append-only decision log.
3. Run the `context-skills` skill once to baseline each file with a
   `last-verified:` date.
4. Decide whether to also run `context-steward` on a schedule (e.g. one
   pass per week, or before each release).
5. After the first real drift report, tune the size limits and
   freshness window in `context-skills/SKILL.md` to match your project.

You do not need both skills active to start — `context-skills` alone is
enough for small projects. Add the steward when the routing layer is
large enough that drift between sessions becomes a real risk.
