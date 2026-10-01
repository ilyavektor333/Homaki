import os
from pathlib import Path
import shutil
import secrets

BASE_DIR = Path(__file__).resolve().parent
data_dir = Path(os.getenv("GAME_SITE_DATA_DIR", str(BASE_DIR))).resolve()
data_dir.mkdir(parents=True, exist_ok=True)

# First deployment: seed the persistent volume with the current local database.
target = data_dir / "database.db"
seed = BASE_DIR / "seed_database.db"

# Persist a session secret on the volume when one is not supplied explicitly.
if not os.getenv("SESSION_SECRET"):
    secret_file = data_dir / ".session_secret"
    if secret_file.exists():
        os.environ["SESSION_SECRET"] = secret_file.read_text(encoding="utf-8").strip()
    else:
        generated = secrets.token_urlsafe(48)
        secret_file.write_text(generated, encoding="utf-8")
        os.environ["SESSION_SECRET"] = generated

if not target.exists() and seed.exists():
    shutil.copy2(seed, target)

import uvicorn

port = int(os.getenv("PORT", "8000"))
uvicorn.run("main:app", host="0.0.0.0", port=port)
