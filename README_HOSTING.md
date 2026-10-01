# GameSite — deployment

This build is prepared for a host with a persistent volume, such as Railway.

## Environment variables

- `GAME_SITE_DATA_DIR=/data` — persistent SQLite database location.
- `SESSION_SECRET` — optional; if omitted, the app generates and persists one on the volume.
- `SESSION_COOKIE_SECURE=true` — enable secure cookies on HTTPS hosting.
- `PORT` — supplied by the host automatically.
- `ADMIN_INITIAL_PASSWORD` — optional fallback password only for creating the Admin account if the database is empty.

On first production start, `seed_database.db` is copied to `/data/database.db` if no database exists there. This preserves the current local database, including the system admin account.

## Railway

Build: Dockerfile
Start: `python start_prod.py` is the Docker CMD.

Attach a persistent Volume at `/data`.
