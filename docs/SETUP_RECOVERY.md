# Legacy Setup Signing Key Recovery

If the signing key is the old public value `temporary-key-will-be-replaced`,
authentication returns HTTP 503 until an operator replaces it locally. Treat
the installation as potentially compromised: anyone who knew the key could
forge tokens before this protection was installed.

1. Restrict network access and stop **all** Linguard processes and containers,
   including every replica. Back up the database and configuration securely.
   Do not delete the database or config to bypass the check.
2. Locate the active database URL in `linguard.config.json` (or the file named
   by `LINGUARD_CONFIG_PATH`). Credentials in this file are sensitive.
3. For SQLite, on the host with direct access to the actual database file, run
   the following with its absolute path as the argument. For a container volume,
   use a trusted temporary container mounting the same volume while Linguard is
   stopped. Include SQLite WAL and SHM files in backups if present.

   ```bash
   python3 - /absolute/path/to/linguard.db <<'PY'
   import secrets
   import sqlite3
   import sys
   from pathlib import Path

   db = sqlite3.connect(Path(sys.argv[1]).resolve().as_uri() + "?mode=rw", uri=True)
   try:
       db.execute("BEGIN IMMEDIATE")
       rows = db.execute("SELECT id, secret_key FROM global_settings").fetchall()
       if len(rows) != 1 or rows[0][1] != "temporary-key-will-be-replaced":
           raise RuntimeError("Expected exactly one settings row with the legacy key; no changes made")
       db.execute(
           "UPDATE global_settings SET secret_key = ?, disable_auth = 0 WHERE id = ?",
           (secrets.token_urlsafe(48), rows[0][0]),
       )
       db.commit()
       print("Signing key rotated; authentication enabled.")
   finally:
       db.close()
   PY
   ```

4. For PostgreSQL or MySQL, have a trusted database administrator perform the
   equivalent transaction: lock and verify there is exactly one settings row
   with the legacy key, replace it with a securely generated random secret of
   at least 32 characters, and set `disable_auth` to false. Avoid exposing the
   new secret in shell history, SQL logs, tickets, or terminal recordings.
5. Review users, credentials, settings, and audit records for unauthorized
   changes. Restore from a known-good backup or rotate credentials as needed.
   Restart one backend instance with one worker, sign in again, and resume setup
   if incomplete. See the [deployment warning](DEPLOYMENT.md) for the setup and
   WebSocket limitations. The rotation invalidates all existing access tokens;
   keep access restricted until the installation has been reviewed.
