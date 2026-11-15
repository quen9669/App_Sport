#!/bin/sh
# Every BACKUP_EVERY_HOURS hours: copy the new nightly copies to the encrypted
# Drive folder, then delete the Drive copies older than BACKUP_REMOTE_DAYS days.
#
# rclone reads its configuration from environment variables set in Coolify
# (RCLONE_CONFIG_GDRIVE_* for Google Drive, RCLONE_CONFIG_SPORT_* for the
# encryption layer), so no config file is needed.
set -eu

SOURCE="${BACKUP_SOURCE:-/data/backups}"
REMOTE="${BACKUP_REMOTE:-sport:}"
EVERY_HOURS="${BACKUP_EVERY_HOURS:-6}"
KEEP_DAYS="${BACKUP_REMOTE_DAYS:-30}"

while true; do
  echo "$(date -u +%FT%TZ) backup: copy ${SOURCE} -> ${REMOTE}"
  # "copy" never deletes on the Drive side: a copy removed locally stays safe.
  if rclone copy "$SOURCE" "$REMOTE" --include "app_sport-*.db" --stats-one-line -v \
     && rclone delete "$REMOTE" --min-age "${KEEP_DAYS}d" -v; then
    echo "$(date -u +%FT%TZ) backup: ok"
    date -u +%s > /tmp/last-success
  else
    echo "$(date -u +%FT%TZ) backup: FAILED (will retry next round)"
  fi
  sleep "$((EVERY_HOURS * 3600))"
done
