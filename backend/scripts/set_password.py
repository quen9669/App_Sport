"""Choose the app password: ``make set-password``.

The password is typed twice (it never appears on screen) and only its Argon2
fingerprint is written to ``.env`` as ``APP_PASSWORD_HASH``. Restart the app
afterwards. To remove the login screen again (only on the PC), empty that line.
"""

import getpass
import re
import sys
from pathlib import Path

from app.services.auth import hash_password

MIN_LENGTH = 10
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def write_hash(env_file: Path, password_hash: str) -> None:
    """Replace (or add) the APP_PASSWORD_HASH line, leaving every other line as is."""
    # Single quotes: the fingerprint contains "$", which must not be read as a variable.
    line = f"APP_PASSWORD_HASH='{password_hash}'"
    text = env_file.read_text() if env_file.exists() else ""
    if re.search(r"^APP_PASSWORD_HASH=.*$", text, flags=re.MULTILINE):
        text = re.sub(r"^APP_PASSWORD_HASH=.*$", lambda _m: line, text, flags=re.MULTILINE)
    else:
        text = text + ("" if text.endswith("\n") or not text else "\n") + line + "\n"
    env_file.write_text(text)


def main() -> int:
    password = getpass.getpass("Nouveau mot de passe de l’app : ")
    if len(password) < MIN_LENGTH:
        print(f"Trop court : au moins {MIN_LENGTH} caractères.")
        return 1
    if getpass.getpass("Retape-le : ") != password:
        print("Les deux mots de passe ne sont pas identiques.")
        return 1
    write_hash(ENV_FILE, hash_password(password))
    print(f"Mot de passe enregistré (empreinte seulement) dans {ENV_FILE}. Relance l’app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
