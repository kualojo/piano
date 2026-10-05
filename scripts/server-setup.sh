#!/usr/bin/env bash
# Runs on the cPanel server after each deploy. Safe to run again and again.
set -euo pipefail
APP="${1:-$HOME/piano}"
cd "$APP"

echo "== Server check"
echo "host: $(hostname)  user: $(whoami)"
PHP=$(command -v php || echo /usr/local/bin/php)
"$PHP" -r 'echo "php ", PHP_VERSION, "\n"; $d = ini_get("disable_functions"); echo "proc_open: ", (function_exists("proc_open") && !str_contains($d, "proc_open")) ? "allowed" : "BLOCKED", "\n"; echo "curl: ", extension_loaded("curl") ? "yes" : "NO", "\n";' || echo "php CLI not found"

# Newest Python 3.9+ we can find (CloudLinux keeps extra versions in /opt/alt)
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3.9 /opt/alt/python31{3,2,1,0}/bin/python3 /opt/alt/python39/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    PY=$(command -v "$c"); break
  fi
done
if [ -z "$PY" ]; then
  echo "!! No Python 3.9 or newer found. In cPanel open 'Setup Python App' and create an app with Python 3.11, then deploy again."
  for d in "$HOME"/virtualenv/*/3.1*/bin/python; do [ -x "$d" ] && PY="$d" && break; done
  [ -z "$PY" ] && exit 1
fi
echo "python: $PY ($("$PY" --version 2>&1))"

if [ ! -x .venv/bin/python ]; then
  echo "== Creating .venv"
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r converter/requirements.txt
.venv/bin/python -c 'import pymupdf; print("pymupdf", pymupdf.__version__)'

mkdir -p storage/jobs && chmod 700 storage storage/jobs
if [ ! -f config.php ]; then
  cp config.example.php config.php && chmod 600 config.php
  echo "!! Created config.php from the example. Edit base_url (and Stripe keys later) in File Manager."
fi

# Daily clean-up of old uploads
LINE="17 3 * * * $PHP $APP/scripts/cleanup.php >/dev/null 2>&1"
if command -v crontab >/dev/null; then
  ( crontab -l 2>/dev/null | grep -v 'scripts/cleanup.php' ; echo "$LINE" ) | crontab - && echo "cron: cleanup scheduled"
else
  echo "!! crontab not available over SSH; add this in cPanel > Cron Jobs: $LINE"
fi

echo "== Deployed $(git -C "$APP" rev-parse --short HEAD 2>/dev/null || date -u +%FT%TZ)"
