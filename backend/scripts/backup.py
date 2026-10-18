"""Back up or restore the database by hand.

make backup                      # a copy now, like the nightly one
make restore                     # list the copies
make restore f=app_sport-....db  # put one back (stop the app first)
"""

import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.db.types import utc_now
from app.services.backup import backup_database, list_backups, restore_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", nargs="?", const="", default=None, metavar="FILE")
    args = parser.parse_args(argv)
    settings = get_settings()
    backup_dir = Path(settings.backup_dir)

    if args.restore is None:
        target = backup_database(settings.database_url, backup_dir, settings.backup_keep, utc_now())
        print(f"Sauvegarde : {target}" if target else "Pas de base SQLite à sauvegarder.")
        return 0
    if not args.restore:
        copies = list_backups(backup_dir)
        print("\n".join(p.name for p in copies) or "Aucune sauvegarde.")
        return 0
    backup = Path(args.restore)
    if not backup.is_absolute() and not backup.exists():
        backup = backup_dir / backup
    aside = restore_database(settings.database_url, backup)
    print(f"Base restaurée depuis {backup.name}. L’ancienne est gardée dans {aside}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
