#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VPS_HOST="${VPS_HOST:?VPS_HOST is required}"
VPS_USER="${VPS_USER:-newsica}"
VPS_PORT="${VPS_PORT:-22}"
VPS_APP_DIR="${VPS_APP_DIR:-/opt/newsica_tv}"
VPS_SSH_KEY="${VPS_SSH_KEY:-}"
DEPLOY_RESTART="${DEPLOY_RESTART:-none}"
NEWSICA_VPS_ENV_B64="${NEWSICA_VPS_ENV_B64:-}"

SSH_OPTS=(
  -p "$VPS_PORT"
  -o BatchMode=yes
  -o StrictHostKeyChecking=accept-new
)

if [ -n "$VPS_SSH_KEY" ]; then
  SSH_OPTS=(-i "$VPS_SSH_KEY" "${SSH_OPTS[@]}")
fi

remote="${VPS_USER}@${VPS_HOST}"

ssh "${SSH_OPTS[@]}" "$remote" "sudo install -d -m 755 -o '$VPS_USER' -g '$VPS_USER' '$VPS_APP_DIR'"

rsync -az --delete \
  -e "ssh ${SSH_OPTS[*]}" \
  --exclude '.git/' \
  --exclude '.github/' \
  --exclude '.env' \
  --exclude '.DS_Store' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '.cache/' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude '.venv_ace_step/' \
  --exclude '.venv_tts_spike/' \
  --exclude 'frontend/node_modules/' \
  --exclude 'node_modules/' \
  --exclude 'runtime/' \
  --exclude 'tmp/' \
  --exclude 'output/' \
  --exclude 'assets/' \
  --exclude 'kokoro-v1.0.onnx' \
  --exclude 'voices-v1.0.bin' \
  "$ROOT_DIR/" "$remote:$VPS_APP_DIR/"

if [ -n "$NEWSICA_VPS_ENV_B64" ]; then
  printf '%s' "$NEWSICA_VPS_ENV_B64" | base64 --decode | ssh "${SSH_OPTS[@]}" "$remote" \
    "umask 077 && cat > '$VPS_APP_DIR/.env'"
fi

ssh "${SSH_OPTS[@]}" "$remote" "set -e
cd '$VPS_APP_DIR'
mkdir -p runtime tmp assets/music assets/ai_music assets/generated
if [ ! -f .env ]; then
  echo 'Missing $VPS_APP_DIR/.env. Create it on the VPS or pass NEWSICA_VPS_ENV_B64.' >&2
  exit 20
fi
python3 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/pip install -r requirements.txt
if [ -f frontend/package-lock.json ]; then
  cd frontend
  npm ci
  npm run build
  cd ..
fi
bash -n manage.sh
venv/bin/python -m py_compile src/dashboard.py src/preparation_agent.py src/generation_worker.py
case '$DEPLOY_RESTART' in
  none)
    ./manage.sh status || true
    ;;
  start)
    ./manage.sh start
    ./manage.sh status
    ;;
  restart)
    ./manage.sh restart
    ./manage.sh status
    ;;
  *)
    echo 'Unsupported DEPLOY_RESTART=$DEPLOY_RESTART. Use none, start or restart.' >&2
    exit 21
    ;;
esac
"
