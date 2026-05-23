#!/bin/bash
REPO_ROOT=${1:-.}
mkdir -p "$REPO_ROOT/.ai-context"

cat > "$REPO_ROOT/.ai-context/README.md" << 'TEMPLATE'
# AI Context Routing System
Entry point for AI agents.
## Precedence
1. AGENTS.md - behavior rules
2. Actual repo files - truth
3. Local vault - scopes/gates
4. Notion - read-only
5. .ai-context - routing aid only
---
Last verified: 2026-05-23
TEMPLATE

cat > "$REPO_ROOT/.ai-context/current-state.md" << 'TEMPLATE'
# Current State
Current branch: [git branch --show-current]
Implementation progress: Starting
---
Last verified: 2026-05-23
TEMPLATE

cat > "$REPO_ROOT/.ai-context/task-router.md" << 'TEMPLATE'
# Task Routing
| Task | Start File | Validate |
|------|-----------|----------|
| Task 1 | path/to/file | command |
---
Last verified: 2026-05-23
TEMPLATE

cat > "$REPO_ROOT/.ai-context/validation.md" << 'TEMPLATE'
# Validation Commands
## Single file
command here
## Full affected
command here
---
Last verified: 2026-05-23
TEMPLATE

cat > "$REPO_ROOT/.ai-context/docs-sync.md" << 'TEMPLATE'
# Documentation Sync
Your vault: source of truth
Notion: read-only visibility
Repo: working copy
---
Last verified: 2026-05-23
TEMPLATE

cat > "$REPO_ROOT/.ai-context/glossary.md" << 'TEMPLATE'
# Glossary
Term: Definition
---
Last verified: 2026-05-23
TEMPLATE

cat > "$REPO_ROOT/.ai-context/context-budget.md" << 'TEMPLATE'
# Context Budget
Read order: 30-40 minutes
Token savings: 30-40% per task
---
Last verified: 2026-05-23
TEMPLATE

cat > "$REPO_ROOT/.ai-context/stewardship.md" << 'TEMPLATE'
# Stewardship
## Checklist
- [ ] Paths exist?
- [ ] Commands work?
- [ ] Line counts OK?
---
Last verified: 2026-05-23
TEMPLATE

echo "✅ Context system initialized"
