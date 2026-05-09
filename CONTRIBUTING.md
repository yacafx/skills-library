# Contributing

Thanks for contributing to this skills library.

## Goals

- Keep skills portable across clients.
- Keep instructions practical and explicit.
- Keep changes easy to review.

## Skill structure

Add each skill under `skills/<skill-name>/`:

```text
skills/
  <skill-name>/
    SKILL.md
    references/   # optional
    scripts/      # optional
    assets/       # optional
```

## Authoring rules

- Use standards-first frontmatter in `SKILL.md`:
  - Required: `name`, `description`
- Keep trigger behavior explicit in the skill body when needed.
- Keep product-specific install/config details in repo docs, not inside skill logic.
- Keep `SKILL.md` focused; move deep examples into `references/`.

## Naming and scope

- Skill folder and `name` should match.
- Use lowercase and hyphenated names (for example `problem-decomposition`).
- One skill should solve one clear workflow/problem.

## Contribution flow

1. Create or update files in one skill folder.
2. Validate links and referenced file paths.
3. Run local validation: `python3 scripts/validate_skills.py`.
4. Test prompt examples manually in at least one client.
5. Open a PR with:
   - what changed
   - why it changed
   - how you tested it

## Commit guidance

- Prefer small commits with one intent each.
- Good pattern:
  - `add <skill-name> skill`
  - `improve <skill-name> templates`
  - `update docs for installation`

## Pull request checklist

- [ ] Skill remains portable and standards-first
- [ ] `SKILL.md` purpose and trigger behavior are clear
- [ ] `references/` content matches `SKILL.md` flow
- [ ] Frontmatter includes required fields (`name`, `description`)
- [ ] Skill folder name matches `name` in `SKILL.md`
- [ ] Local validator passes
- [ ] README/docs updated when installation guidance changes
