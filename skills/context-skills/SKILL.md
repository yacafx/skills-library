---
name: context-skills
description: "Maintain and validate a lightweight AI context routing system. Use when: updating context files, detecting context drift, validating paths and commands, updating current state after completions. Always verify findings against actual repo files—context routing is an index, not source of truth."
---

# Context Skills

A reusable skill for maintaining a lightweight, file-based context routing
system that helps AI assistants and humans navigate a codebase without
loading everything into the context window. The skill treats the routing
layer as an **index**, not as the source of truth: every claim is verified
against the actual repository before it is trusted.

## Purpose

Most projects accumulate scattered documentation: half-finished READMEs,
out-of-date setup guides, decisions buried in chat logs. A routing system
fixes this by maintaining a small, predictable set of files that tell any
reader (human or AI) where to look next. This skill keeps that routing
layer accurate, lean, and trustworthy.

## When to Use

Invoke this skill when any of the following is true:

- You are about to update a context file (architecture notes, current
  state, command index, decision log).
- You suspect **drift**: the routing files describe code, paths, or
  commands that no longer match reality.
- You finished a task and the "current state" entry needs to reflect what
  changed.
- You want to validate that every path and shell command referenced in
  the routing files still resolves to something real.
- A new contributor (human or agent) is onboarding and you need to
  confirm the index is correct before they rely on it.

If none of these apply, skip the skill—routing maintenance is overhead
unless the index is actively being used or actively wrong.

## Precedence Rules (Immutable)

When the routing files disagree with the repository, the repository
**always** wins. The following ordering is non-negotiable:

1. **Working tree** — what `git status` and the filesystem show right now.
2. **Committed code** — what `HEAD` contains.
3. **Tests and CI configuration** — what is actually executed.
4. **Decision log entries** — recorded rationale, dated.
5. **Routing files** (this skill's outputs) — pointers and summaries.
6. **External docs / chat history** — lowest authority.

If a routing file claims `src/api/v2/handler.ts` exists but the file is
not present, the routing file is wrong. Never patch reality to match the
index.

## File Size Limits (Adaptive)

Routing files must stay small enough to load quickly. Use these soft
limits, and adapt when the project genuinely needs more:

| File type              | Target  | Hard ceiling |
| ---------------------- | ------- | ------------ |
| Top-level index        | 40 lines | 80 lines     |
| Per-area routing note  | 80 lines | 150 lines    |
| Current-state snapshot | 30 lines | 60 lines     |
| Command index          | 50 lines | 100 lines    |
| Decision log entry     | 20 lines | 40 lines     |

If a file exceeds the hard ceiling, split it. If splitting fragments the
information past usefulness, raise the ceiling explicitly in the file's
header and note why. Adaptation is allowed; silent bloat is not.

## Drift Detection Checklist

Run through these seven checks every time the skill is invoked. Mark each
as PASS, FAIL, or SKIP (with reason). Report all FAILs.

1. **Paths resolve.** Every file path mentioned in routing files exists
   in the working tree. Verify with `ls` or equivalent, not from memory.
2. **Commands execute.** Every shell command listed (install, build,
   test, lint, run) succeeds, or at minimum parses. Run a dry version
   where possible.
3. **Entry points match.** The main binary, server, or library entry
   referenced in the index matches what the build system actually
   produces.
4. **Current state is current.** The "current state" file's last-updated
   date is within the project's freshness window (default: 14 days) or
   has been touched since the last merged change.
5. **Decisions reflect code.** Each active decision-log entry has a
   corresponding implementation or an explicit "pending" marker.
6. **No orphan references.** Routing files do not link to deleted files,
   removed scripts, or retired services.
7. **No duplicate authority.** A given fact (e.g. "the test command is
   X") appears in exactly one routing file; others link to it.

## Update Policy

When you find drift, follow this policy:

- **Propose, don't impose.** Show the diff and the evidence (file path,
  command output, commit hash) that supports the change.
- **One change per concern.** A drift fix and a content improvement are
  separate edits.
- **Date every update.** Add or refresh the `last-verified:` field at
  the top of any routing file you touch.
- **Never invent paths.** If a referenced file is missing and you cannot
  determine the correct replacement from the repo, mark the entry
  `UNRESOLVED` and surface it in the report.
- **Preserve precedence.** Do not "fix" a routing file by editing source
  code to match it. The repo is the source of truth.

## Report Format

Every run of this skill produces a short structured report:

```
Context routing check — <YYYY-MM-DD>
Scope: <which routing files were inspected>

Drift detected:
  - [HIGH] <file>: <one-line description, evidence>
  - [MED]  <file>: <one-line description, evidence>
  - [LOW]  <file>: <one-line description, evidence>

Proposed updates:
  - <file>: <diff summary>

Unresolved:
  - <file>: <what could not be verified and why>

Verified clean:
  - <file>, <file>, ...
```

Keep the report under 40 lines. If there is more to say, attach a
separate notes file and link it from the report.

## Success Criteria

A context-routing maintenance pass is successful when **all** of the
following hold:

- Every routing file referenced in the report has a `last-verified:`
  date no older than this run.
- Every FAIL from the drift checklist has either a proposed fix or an
  `UNRESOLVED` marker with a reason.
- No new content was added that duplicates an existing fact in another
  routing file.
- The total token cost of the routing layer (sum of all routing files)
  has not grown by more than 10% in this pass, unless growth is
  explicitly justified in the report.
- A reader following the routing files reaches the correct source file
  in three hops or fewer for any common task.

## Anti-patterns

Avoid these failure modes:

- **Routing-as-documentation.** Routing files point to where the real
  documentation lives; they are not the documentation themselves.
- **Speculative entries.** Do not add routes for files or commands that
  do not yet exist, even if planned.
- **Silent edits.** Every change to a routing file is reported, even
  one-line fixes.
- **Skipping verification.** Do not trust a previous run's report. Re-verify.
- **Editing without evidence.** If you cannot cite a path, command output,
  or commit, do not change the routing file.

## Integration

This skill is designed to pair with the `context-steward` agent, which
performs the same checks autonomously and proposes diffs without
committing. Either entry point is valid: invoke this skill directly when
you want to run a check yourself, or hand off to the steward when you
want a guardian process to watch the routing layer over time.
