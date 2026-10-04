#!/usr/bin/env bash
# One-command start (macOS / Linux): checks Docker, asks for the NVIDIA key once, starts the stack.
set -euo pipefail
cd "$(dirname "$0")"

echo
echo " Hospital Workflow Agent"
echo " -----------------------"

if ! docker info >/dev/null 2>&1; then
  echo " Docker is not running. Install Docker (https://docs.docker.com/get-docker/), start it, then re-run."
  exit 1
fi

[ -f .env ] || cp .env.example .env

if grep -qE '^NVIDIA_API_KEY=(nvapi-your-key-here)?$' .env; then
  echo
  echo " An NVIDIA API key is needed (free): https://build.nvidia.com"
  echo " Open any model, click 'Get API Key', then paste it below. It is saved only to .env."
  read -rsp "  NVIDIA API key (input hidden): " KEY; echo
  [ -n "$KEY" ] || { echo " No key entered."; exit 1; }
  tmp=$(mktemp)
  awk -v k="$KEY" '/^NVIDIA_API_KEY=/{print "NVIDIA_API_KEY=" k; next} {print}' .env > "$tmp" && mv "$tmp" .env
  echo "  > API key saved to .env"
fi

echo "  > Building and starting containers (first run: 3-5 minutes, includes data generation and model training)..."
docker compose up --build -d

echo "  > Waiting for the app to become ready..."
for _ in $(seq 1 120); do
  if curl -s -o /dev/null -f http://localhost:8080/api/health; then
    echo "  > Ready: http://localhost:8080   (demo login: admin / admin123)"
    echo "    Stop with: docker compose down"
    (command -v open >/dev/null && open http://localhost:8080) || (command -v xdg-open >/dev/null && xdg-open http://localhost:8080) || true
    exit 0
  fi
  sleep 3
done
echo " The app did not become ready in time. Check logs with: docker compose logs backend"
exit 1
