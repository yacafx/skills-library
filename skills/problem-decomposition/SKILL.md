---
name: problem-decomposition
description: >
  Run this skill only when explicitly invoked with `decompose:` (for example,
  `decompose: ...`) or `$problem-decomposition`. Guide the user from a vague
  problem to an actionable artifact by reframing the issue, mapping factors and
  causality, prioritizing leverage points, clarifying constraints/success
  criteria, and synthesizing into a structured prompt, spec, or investigation
  brief.
---

# Problem Decomposition
## Invocation contract

Run only when explicitly called with `decompose: <problem>` or `$problem-decomposition`.
If the user says something vague like "I'm stuck" without explicit invocation, do not start this workflow.

## Modes

- **Coaching** (default): step-by-step interaction.
- **Execution**: user provides enough context or says "just do it".
- **Quick**: run faster; infer missing details and ask for a final confirmation before output.

## Per-step behavior

1. Ask the guiding question. Skip if already answered.
2. Wait for input.
3. Review only when needed (gap, overlap, vagueness).
4. Do not ask "ready for next step?" unless something needs correction.

## Adaptive guidance

- Short/vague responses, asks for examples → read [references/GUIDANCE.md](references/GUIDANCE.md) for scaffolding examples and probing questions. Use them to help the user.
- Detailed, specific responses → minimal feedback, move forward.
- User says "next" or "speed up" → lighter touch or switch to execution mode.
Do not load GUIDANCE.md unless the user needs it.

## Workflow steps

### Step 1: Problem

Ask: "Describe the problem in 1-2 sentences, as you perceive it right now. Don't analyze it yet — just write it as it comes."

### Step 2: Reframe

Ask: "Before solving, how else could we frame this? Is this mainly a symptom, root cause, constraint, or decision?"
Capture 1 primary framing and 1-2 alternate framings.

### Step 3: Goal

Ask: "What does 'solved' look like? What do you want to achieve?"

Skip if the user already stated a clear goal in step 1.

### Step 4: List factors

Ask: "What people, processes, resources, decisions, or circumstances are involved in this problem?"

Adapt framing to domain. Encourage at least 5-7 factors. If the user struggles, use probing questions from GUIDANCE.md.

### Step 5: Group

Ask: "Looking at your factors, which ones are similar or of the same type? Group them into categories."

Categories should be meaningful — avoid generic labels like "other" or "misc."

### Step 6: Connect

Ask: "Which factors cause or worsen others? Is there one that, if resolved, changes several of the rest?"

Help the user see causal chains, not just associations.

### Step 7: Prioritize

Ask: "If you could only act on three factors, which would they be and why?"

Focus on impact, not ease.

### Quality self-assessment (after step 7)

Pause and ask:
- "Looking at your factors and groups — is anything important missing?"
- "Do any of these overlap or say the same thing differently?"

This is a prompt for the user to reflect, not an agent validation. Accept their answer and move on.

### Step 8: Constraints

Ask: "What limits what you can do?"

Adapt framing to domain:
- Technical: stack, time, team size, backwards compatibility, performance
- Personal: values, energy, money, relationships, location
- Business: budget, regulation, market window, brand, contracts

Skip if the user already stated constraints earlier.

### Step 9: Success criteria

Ask: "How will you know it turned out well? What's measurable or observable?"

Adapt to domain. Skip if the goal in step 2 already defines this clearly.

### Step 10: Knowns, assumptions, unknowns

Ask:
- "What do we know as facts?"
- "What assumptions are we making?"
- "What important unknowns remain?"
Capture concise bullets for each section. If none, mark explicitly as none.

### Step 11: Final output

Before producing output, read [references/TEMPLATE.md](references/TEMPLATE.md) and follow the format exactly.

Ask: "Want this as an AI prompt, a spec, an investigation brief, or both prompt/spec?"

Choose default based on context:
- Goal involves getting help from AI → default to prompt
- Goal involves planning, delegation, or documentation → default to spec
- Goal is still unclear and needs evidence-gathering first → default to investigation brief
- If unclear → ask

In Quick mode, present inferred constraints/success criteria/unknowns first and ask for confirmation before producing the final artifact.
Present the output in chat.

## Save to file

After presenting the final output, offer: "Want me to save this to a file? If so, tell me the path and filename."

Suggested names:
- Spec: `<problem-slug>-spec-YYYY-MM-DD.md`
- Prompt: `<problem-slug>-prompt-YYYY-MM-DD.md`
- Investigation brief: `<problem-slug>-investigation-YYYY-MM-DD.md`

If the user provided a project path, suggest:
- `<project>/docs/specs/<problem-slug>-spec-YYYY-MM-DD.md`

If user provides a path → write the file. If user declines → continue.

## Optional downstream handoff

After Step 11, this skill can hand off to `spec-driven-development`.

Required handoff fields:
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

## Step 12: Challenge (optional)

Invite a stress test for blind spots and assumptions.
If user accepts:
- Analyze flaws, gaps, risks, inconsistencies, and unstated assumptions.
- Present top 3-5 issues with why each matters and a suggested fix.
- End by offering revision.
If user declines:
- Acknowledge and close.
