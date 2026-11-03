#!/usr/bin/env bash
# Deploy the price collector from git to the data collection server.
#
#   ./deploy.sh            deploy committed code
#   ALLOW_DIRTY=1 ./deploy.sh   deploy with uncommitted changes in this folder
#
# The server runs the collector with Docker Compose from REMOTE_DIR, which is
# bind-mounted into the container. docker-compose.yml and .env (MONGO_URL) on
# the server are not overwritten by this script, but it refuses to deploy
# unless the Mongo URL lives in .env and not in docker-compose.yml.
set -euo pipefail

HOST="${COLLECTOR_HOST:-ubuntu@ec2-54-235-238-247.compute-1.amazonaws.com}"
KEY="${COLLECTOR_SSH_KEY:-$HOME/aws/east_runner.pem}"
REMOTE_DIR="${COLLECTOR_DIR:-/home/ubuntu}"
SERVICE="unified_price_system"
FILES=(unified_price_system3.py requirements.txt Dockerfile .dockerignore)

cd "$(dirname "$0")"

if [ -z "${ALLOW_DIRTY:-}" ] && [ -n "$(git status --porcelain -- .)" ]; then
    echo "Uncommitted changes in $(pwd); commit first or set ALLOW_DIRTY=1" >&2
    exit 1
fi

python3 -m py_compile unified_price_system3.py

SSH=(ssh -i "$KEY" -o BatchMode=yes "$HOST")
STAMP="$(date +%Y%m%d%H%M%S)"

echo "Checking server config..."
"${SSH[@]}" "cd '$REMOTE_DIR' && bash -s" <<'EOF' || { echo "Fix the server config above, then deploy again." >&2; exit 1; }
problems=0
if ! grep -Eq '^MONGO_URL=.+' .env 2>/dev/null; then
    echo "  .env is missing or has no MONGO_URL (see .env.example)" >&2
    problems=1
fi
if grep -Eq 'mongodb(\+srv)?://' docker-compose.yml; then
    echo "  docker-compose.yml still contains a Mongo URL; move it to .env" >&2
    problems=1
fi
if ! grep -q 'env_file' docker-compose.yml; then
    echo "  docker-compose.yml does not load .env (add 'env_file: .env' to the service)" >&2
    problems=1
fi
[ "$problems" = 0 ] || exit 1
chmod 600 .env
EOF

echo "Backing up current server copy..."
"${SSH[@]}" "cd '$REMOTE_DIR' && cp unified_price_system3.py 'unified_price_system3.py.bak-$STAMP'"

echo "Copying ${FILES[*]} to $HOST:$REMOTE_DIR"
scp -i "$KEY" -o BatchMode=yes "${FILES[@]}" "$HOST:$REMOTE_DIR/"

echo "Rebuilding and restarting $SERVICE..."
"${SSH[@]}" "cd '$REMOTE_DIR' && docker compose up -d --build $SERVICE && docker compose ps $SERVICE"

echo "Deployed $(git rev-parse --short HEAD). Rollback copy: unified_price_system3.py.bak-$STAMP"
echo "Follow logs: ssh -i $KEY $HOST 'docker compose -f $REMOTE_DIR/docker-compose.yml logs -f $SERVICE'"
