#!/bin/bash
# deploy_bootstrap.sh
# This script is for the bootstrap VM (with IP=10.0.62.44).
# It deploys:
#   1) A bootstrap container on port 8000
#   2) A second node container on port 8001
#
# The script auto-detects the machine's IP address,
# then bind-mounts the project root (one level up from scripts/) into /app.

# 1) Determine the script's directory and the project root.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 2) Change to the project root directory so that Docker sees app.py, etc.
cd "$PROJECT_ROOT"

# 3) Detect this machine's IP address
MY_IP=$(hostname -I | awk '{print $1}')

# 4) Define ports
BOOTSTRAP_PORT=8000
SECOND_NODE_PORT=8001

echo "Detected IP: ${MY_IP}"
echo "Using project directory: ${PROJECT_ROOT}"

# 5) Start the bootstrap container
echo "Starting bootstrap container on port ${BOOTSTRAP_PORT}..."
docker run -d --name bootstrap \
  -p ${BOOTSTRAP_PORT}:${BOOTSTRAP_PORT} \
  -v "${PROJECT_ROOT}:/app" \
  -e IP=${MY_IP} \
  -e PORT=${BOOTSTRAP_PORT} \
  -e FLASK_ENV=development \
  -e FLASK_DEBUG=1 \
  -e PYTHONUNBUFFERED=1 \
  chord-app \
  python app.py \
    --ip ${MY_IP} \
    --port ${BOOTSTRAP_PORT} \
    --bootstrap \
    --replication_factor 3 \
    --consistency_mode linearizability

# 6) Wait a bit
echo "Waiting 2 seconds..."
sleep 2

# 7) Start the second node on the same VM
echo "Starting second node container on port ${SECOND_NODE_PORT}..."
docker run -d --name node1 \
  -p ${SECOND_NODE_PORT}:${SECOND_NODE_PORT} \
  -v "${PROJECT_ROOT}:/app" \
  -e IP=${MY_IP} \
  -e PORT=${SECOND_NODE_PORT} \
  -e FLASK_ENV=development \
  -e FLASK_DEBUG=1 \
  -e PYTHONUNBUFFERED=1 \
  chord-app \
  sh -c "sleep 1 && python app.py \
    --ip ${MY_IP} \
    --port ${SECOND_NODE_PORT} \
    --bootstrap_ip ${MY_IP} \
    --bootstrap_port ${BOOTSTRAP_PORT}"
