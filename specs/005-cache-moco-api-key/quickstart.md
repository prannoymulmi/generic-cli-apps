# Quickstart: The Local Moco API Key Cache

After this feature, `moco-filler` asks for your API key **at most once**.
The key is saved to a private per-user file and reused on later runs.

## First run

```bash
moco-filler --month 2026-07
# Moco API key: ********   ← masked prompt (only this once)
```

Once the key authenticates, it is saved silently. Every later run skips
the prompt.

## Where the key is stored

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/moco-filler/credentials.json` |
| Linux | `${XDG_CONFIG_HOME:-$HOME/.config}/moco-filler/credentials.json` |
| Windows | `%APPDATA%\moco-filler\credentials.json` |

- It lives **outside** any git repository, so it can never be committed.
- The file is owner-readable only (`0o600` on macOS/Linux).
- Contents are minimal: `{"schema_version": 1, "token": "<key>"}`.

## Overriding the saved key

Set `MOCO_API_KEY` for a run — it takes precedence over the saved key:

```bash
MOCO_API_KEY="another-key" moco-filler --month 2026-07
```

Once that key authenticates, it is also saved (replacing the previous
one), so subsequent runs need neither the env var nor the prompt.

## Replacing or clearing the saved key

Delete the file with ordinary tools; the next run prompts again:

```bash
# macOS
rm ~/Library/Application\ Support/moco-filler/credentials.json
# Linux
rm "${XDG_CONFIG_HOME:-$HOME/.config}/moco-filler/credentials.json"
```

You don't have to clear it manually if your key was rotated: when Moco
rejects the saved key, the tool deletes it, tells you, and prompts for a
new one in the same run.

## What happens if the key can't be saved

If the file can't be written (read-only disk, permissions), the current
run still completes — you'll see a one-line warning and may be prompted
again next time.

## Developer notes

- Store I/O: `src/moco_filler/credential_store.py` (stdlib-only, atomic
  write, `0o600`).
- Resolution + reject-recovery: `src/moco_filler/auth.py`
  (`authenticate(validate)`).
- Run tests: `pytest tests/test_credential_store.py tests/test_auth.py`.
- The key is never printed or logged; `ApiCredentials.source`
  (`"env" | "store" | "prompt"`) names the origin without exposing the
  token.
