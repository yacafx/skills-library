---
name: rpg-library-curator
description: Audit, classify, deduplicate, document, and safely reorganize tabletop RPG libraries. Use when Codex needs to inspect an RPG collection, triage RPG files from inboxes or download folders, identify exact duplicate PDFs/assets, propose a durable folder structure, document routing rules, or execute an explicitly approved migration of RPG materials.
---

# RPG Library Curator

Curate tabletop RPG libraries by ownership and play use, not only by file type. Treat a library root as canonical and external inboxes or download folders as intake sources.

## Safety Contract

- Start with `audit`, `duplicates`, or `propose`. These modes are read-only.
- Do not create, rename, move, archive, or remove files until the user explicitly approves a written migration manifest.
- Do not permanently delete files. Move redundant exact copies to the system Trash only after the canonical copy has been verified.
- Preserve meaningful editions, translations, previews, errata, source ZIPs, and release snapshots. Equal filename or size is not enough to call two files duplicates.
- Never flatten a self-contained product bundle. Its maps, tokens, handouts, and adventure documents remain together when they are exclusive to that product.

## Inputs

Require a canonical RPG library root. Accept zero or more explicit intake roots. Do not scan unrelated home directories by default.

Use the local library `README.md` as the source of truth when it documents taxonomy or intake sources. If it is absent, propose documentation rather than inventing project-specific rules.

Run the inventory utility for a baseline:

```bash
python3 scripts/audit_rpg_library.py --root <library-root> --root <intake-root>
```

Run exact duplicate detection only when needed:

```bash
python3 scripts/audit_rpg_library.py --hash-duplicates --root <library-root> --root <intake-root>
```

Read [routing policy](references/routing-policy.md) before classifying content or proposing structure.

## Modes

### Audit

1. Inventory every nested folder in the canonical root and each supplied intake root.
2. Review folder names, filenames, PDF metadata/text, archive contents, and visual assets when necessary to determine game, edition, product, and primary use.
3. Separate confirmed RPG material, non-RPG material, and uncertain material. Leave non-RPG material in its source and report it only.
4. Report the existing structure, candidate systems, archive/source packages, and confidence for each proposed classification.

### Duplicates

1. Use SHA-256 to confirm byte-identical candidates.
2. Treat release variants, translated files, previews, print layouts, and bundles as distinct until content review proves otherwise.
3. Report one canonical path, duplicate paths, provenance value, and recommended action for every confirmed duplicate group.
4. Do not deduplicate repeated assets that intentionally make product bundles self-contained.

### Propose

Produce a written manifest before any mutation. For every move, include:

| Source | Destination | Action | Confidence | Reason | Hash |
| --- | --- | --- | --- | --- | --- |

Use these actions only: `move`, `archive`, `trash exact duplicate`, `leave in source`, or `needs review`.

Route confirmed RPG content directly only when game ownership and category are clear. Route confirmed RPG content with uncertain placement to the library `00 Inbox`. Mark a distinct game or setting without an approved home as `New Library Candidate`; do not create that library silently.

### Organize

Proceed only after the user approves the manifest. Apply moves in small batches and verify destination hashes before removing each source. Keep a dated migration manifest under the library archive. Re-run the inventory after each major batch and report discrepancies immediately.

## Routing Principles

- Store game-specific content in its game or setting library.
- Store generic engines separately from games that use them.
- Store reusable maps, tokens, generic sheets, and table-safety tools in shared resources.
- Keep an adventure-exclusive map or handout within its adventure package.
- Keep source ZIPs and replaced releases in the archive of their owning library.
- Use English folder names. Preserve official product titles and original filenames.

Consult the routing policy for the target hierarchy, intake workflow, and duplicate rules.
