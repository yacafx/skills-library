# Problem Decomposition

Practical skill to turn a vague problem into an actionable artifact through structured questioning and prioritization.

## What is in this folder
- `SKILL.md` - runnable skill workflow (invocation, modes, step-by-step process).
- `references/TEMPLATE.md` - output formats for prompt, spec, and investigation brief.
- `references/GUIDANCE.md` - probing prompts and examples when the user is stuck.

## When to use
Use only with explicit invocation:
- `decompose: <problem>`
- `$problem-decomposition`

Do not auto-run this skill on vague messages unless explicitly requested.

## What it produces
One of:
- AI prompt
- spec
- investigation brief
- prompt + spec

## Hybrid flow with Agent Skills
After Step 11 output, this can hand off to `spec-driven-development` using:
- `problem_statement`
- `success_metrics`
- `constraints`
- `in_scope`
- `out_of_scope`
- `risks`
- `open_questions`
- `recommended_direction`

Recommended next flow:
`spec -> plan -> build/test -> review -> ship`
