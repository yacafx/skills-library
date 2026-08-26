# RPG Library Routing Policy

## Target Hierarchy

```text
rpg/
├── 00 Inbox/
│   ├── 01 Unassigned/
│   ├── 02 Needs Review/
│   └── 03 Duplicate Candidates/
├── 01 Games & Settings/
├── 02 Play Engines/
├── 03 Shared Resources/
└── 90 Archive/
    ├── 01 Migration Manifests/
    └── 02 Unassigned Sources/
```

Use a local `90 Archive` within each game or engine library for that library's original downloads, previews, and superseded versions. Use the root archive only for migration records and sources without a confirmed owner.

## Ownership Decision Table

| Content | Home |
| --- | --- |
| Rules, supplements, character sheets, and game-specific GM material | Owning game or setting |
| Setting book, setting map, or licensed adaptation | Owning game or setting |
| Adventure, its exclusive maps, tokens, and handouts | Same adventure package |
| Reusable map, token set, generic reference art, or VTT-ready asset | `03 Shared Resources/01 Reusable Digital Assets` |
| System-neutral GM tables and generators | `03 Shared Resources/02 GM Tools & Random Tables` |
| System-neutral GM sheets | `03 Shared Resources/03 Generic Sheets` |
| Consent and safety tools | `03 Shared Resources/04 Table Safety` |
| Solo emulator or game-neutral engine | `02 Play Engines` |
| Campaign notes, house rules, and active characters | Owning library `My Table` |
| Source ZIP, preview, obsolete release, or translation snapshot | Owning library `90 Archive` |

## Intake Workflow

1. Treat all supplied inboxes and download directories as source roots, never as canonical destinations.
2. Move clear material directly to its approved home.
3. Move confirmed RPG material with uncertain placement to `00 Inbox/01 Unassigned` or `02 Needs Review`.
4. Keep non-RPG files in their original source and report them as out of scope.
5. Move an exact duplicate to Trash only after the canonical destination has been verified. Do not use permanent deletion.

## Duplicate Policy

- A matching SHA-256 confirms an exact duplicate.
- A matching title, filename, or page count does not confirm a duplicate.
- Retain one canonical active copy and one provenance ZIP when the source package is useful.
- Preserve edition changes, errata, previews, print layouts, translations, and meaningful backups.
- Preserve intentional asset repetition inside self-contained bundles.

## Standard Library Template

Create only categories that contain material:

```text
<Game or Setting>/
├── 01 Rules & Supplements/
├── 02 Settings & Worlds/
├── 03 Adventures & Play/
├── 04 Player & GM Materials/
├── 05 My Table/
├── 06 Digital Assets/
└── 90 Archive/
```

Keep a mature existing taxonomy when it is more specific than this template. Do not normalize a well-organized library merely for visual consistency.
