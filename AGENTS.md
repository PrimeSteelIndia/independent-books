# Shared checkout coordination

This checkout is shared by the user, Antigravity, and Codex. Preserve each other's in-progress work.

- Before editing, inspect `git status`, the relevant diff, and the current file. Do not reset, clean, stash, or overwrite unrelated changes.
- Re-read a file immediately before a targeted edit. Build into a separate staging directory when another agent is packaging or publishing.
- Do not run two builds that delete or replace `dist` concurrently. Do not publish another agent's unfinished changes.
- Keep accounting databases and browser profiles out of builds, tests, and source uploads. Test with fresh synthetic databases.
- A clean antivirus scan, unsigned publisher status, or a matching checksum does not establish why Chrome blocked a download. Record artifact hashes and actual scan results; never disable protections or advise customers to bypass a dangerous-download warning.
- Codex release checks live under `tools/release_hardening/`; coordinate changes to `build_installer.ps1`, `launcher.c`, and the separate landing-page directory with Antigravity's current work.
