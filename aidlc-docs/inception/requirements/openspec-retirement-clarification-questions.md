# OpenSpec Retirement Clarification Questions

The approved direction is to make AI-DLC the repository's sole SDLC/specification workflow and
remove the active OpenSpec artifacts. These two decisions define the safe retirement point and the
meaning of archival. Enter one letter after every `[Answer]:` tag.

## Question 1: Retirement Timing

When should the active `openspec/` directory and OpenSpec governance be removed?

**Recommendation: A.** Retiring OpenSpec immediately after the AI-DLC migration package is approved
prevents dual governance during design and construction while still requiring a complete coverage
and traceability check before deletion.

A) **Recommended** - After the amended AI-DLC requirements, migration inventory, and traceability
check are explicitly approved; remove OpenSpec and update `AGENTS.md` and all active references in
the same reviewed change before downstream design or construction

B) Keep OpenSpec read-only through all AI-DLC design and construction, then remove it only after the
implementation and Build and Test stages are complete

C) Remove OpenSpec immediately, before the migration inventory and traceability check are approved

X) Other (please describe after the `[Answer]:` tag below)

## Question 2: Archive Form

What should “archived” mean once OpenSpec is removed from the active repository tree?

**Recommendation: A.** Git history plus an AI-DLC migration inventory preserves provenance and
coverage evidence without leaving a second specification tree in the repository or creating an
unmanaged external file copy.

A) **Recommended** - Preserve the removed files through Git history and record a final migration
inventory with source paths and replacement AI-DLC requirement/task references; do not retain an
additional OpenSpec copy in the working tree

B) Create a repository-external archive bundle in a user-designated location, record its checksum
and migration inventory in AI-DLC, then remove the active files

C) Preserve an OpenSpec snapshot under `aidlc-docs/` after removing `openspec/`

X) Other (please describe after the `[Answer]:` tag below)
