# Output Templates

## Format A: AI Prompt

Produce a self-contained prompt the user can paste into any AI tool:

```
[CONTEXT]
I'm working on: [problem, 1-2 sentences]
My goal is: [goal]

[BACKGROUND]
Key factors involved: [top 3-5 factors from priorities + connections]
These relate because: [key causal connections, 1-2 sentences]

[KNOWN FACTS]
- [fact]
- If none: "None identified."

[ASSUMPTIONS]
- [assumption]
- If none: "No major assumptions beyond stated context."

[UNKNOWNS]
- [unknown]
- If none: "None identified that block action."

[CONSTRAINTS]
[constraints, as bullet points]

[TOP RISKS]
- [risk]
- If none: "No critical risks identified at this stage."

[FIRST ACTIONS]
1. [action]
2. [action]
3. [action]

[REQUEST]
[Specific question or task for the AI]

[SUCCESS CRITERIA]
A good answer will: [criteria as bullet points]
```

## Format B: Spec / Requirements Doc

```markdown
# [Problem Title]

## Problem Statement
[Step 1 content]

## Reframed Problem
- Primary framing: [symptom/root cause/constraint/decision]
- Alternate framings considered: [1-2 bullets]

## Goal
[Step 2 content]

## Scope
### [Category 1]
- Factor...
### [Category 2]
- Factor...

## Key Dependencies & Connections
- [Factor A] → [Factor B]: [how]

## Priorities
1. [Factor] — [rationale]
2. [Factor] — [rationale]
3. [Factor] — [rationale]

## Constraints
- [constraint]

## Known Facts
- [fact]
- If none: None identified.

## Assumptions
- [assumption]
- If none: No major assumptions beyond stated context.

## Unknowns
- [unknown]
- If none: None identified that block action.

## Top Risks
- [risk]
- If none: No critical risks identified at this stage.

## First 3 Actions
1. [action]
2. [action]
3. [action]

## Acceptance Criteria
- [ ] [criterion]
```

## Format C: Investigation Brief

Use when the problem is not yet execution-ready.

```markdown
# [Problem Title] - Investigation Brief

## Current Problem Framing
[Primary framing + alternate framings]

## What We Know
- [fact]

## Key Unknowns
- [unknown]

## Hypotheses To Test
1. [hypothesis]
2. [hypothesis]

## Evidence Plan
1. [what to collect]
2. [how to validate]
3. [decision threshold]

## Next Decision Point
[What decision will be made after investigation]
```

## Choosing the format

- If the user's goal involves getting help from AI → default to Format A
- If the user's goal involves planning, delegation, or documentation → default to Format B
- If the problem is still unclear and needs evidence first → default to Format C
- If unclear → ask
- If user wants both → produce both
