# Central Handoff (D-141)

- Before any task, read `docs/MASTER_HANDOFF.md` sections 0-7 and the active spec it names in `docs/specs/`. Confirm the required versions; stop and report missing or outdated artifacts.
- Never print, log, or write secret values into any file, including keys, passphrases, tokens, credential payloads, or `.env` contents.
- When Regan supplies a `MASTER_HANDOFF_UPDATE` file, apply it verbatim, bump the handoff version and update its date/author, and append the update's section 9 line.
- At the end of every task, append one section 9 line: date, `Codex`, what changed, and the current head hash.
- Never edit handoff sections 3 or 8 except when applying a Regan-supplied update file.
