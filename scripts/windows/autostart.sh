#!/usr/bin/env bash
# Starts App Sport when FRANKS logs in to Windows.
#   make autostart       # add (or update) the shortcut, then start the app now
#   make autostart-off   # remove the shortcut
#   make prod-restart    # stop the running app and start it again (after an update)
# Runs inside WSL, which can call Windows programs (powershell.exe).
#
# Why a shortcut in the Windows "Startup" folder rather than a scheduled task:
# creating a log-on task with `schtasks` needs administrator rights, the Startup
# folder does not. Everything in it is opened at each log-on.
set -euo pipefail

action="${1:-on}"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
distro="${WSL_DISTRO_NAME:-Ubuntu}"

if ! command -v powershell.exe >/dev/null; then
  echo "powershell.exe introuvable : cette commande se lance dans Ubuntu (WSL) sur Windows."
  exit 1
fi

# Runs a PowerShell command and drops the Windows line endings (\r) of its output.
ps() { powershell.exe -NoProfile -Command "$1" | tr -d '\r'; }

startup="$(ps "[Environment]::GetFolderPath('Startup')")"
shortcut="$startup\\App Sport.lnk"

# Opens the shortcut, as Windows does at log-on: the app starts without a window.
start_now() {
  ps "Start-Process -FilePath '$shortcut'"
  echo "App Sport démarre (une minute environ). Journal : tail -n 30 backend/data/prod.log"
}

case "$action" in
  off)
    ps "Remove-Item -LiteralPath '$shortcut' -ErrorAction SilentlyContinue"
    echo "Démarrage automatique retiré. L'app en cours tourne jusqu'au prochain redémarrage."
    ;;
  restart)
    # pkill exits with 1 when nothing was running: that's fine here.
    pkill -f "uvicorn app.main:app" || true
    sleep 2
    start_now
    ;;
  on)
    # The app refuses to start in production without a password: check it first.
    if ! grep -qE "^APP_PASSWORD_HASH=['\"]?\\\$argon2" "$repo/.env" 2>/dev/null; then
      echo "Choisis d'abord un mot de passe : make set-password"
      exit 1
    fi
    # The shortcut runs a hidden PowerShell, which starts WSL, which runs start-app.sh.
    # WindowStyle 7 = minimised, so even the brief PowerShell start does not pop up.
    ps "\$s = (New-Object -ComObject WScript.Shell).CreateShortcut('$shortcut');
        \$s.TargetPath = 'powershell.exe';
        \$s.Arguments = '-NoProfile -WindowStyle Hidden -Command wsl.exe -d $distro -- bash $repo/scripts/windows/start-app.sh';
        \$s.WindowStyle = 7;
        \$s.Description = 'Démarre App Sport (make prod)';
        \$s.Save()"
    echo "App Sport démarrera à chaque ouverture de session Windows."
    start_now
    ;;
  *)
    echo "Usage : autostart.sh on|off|restart"
    exit 1
    ;;
esac
