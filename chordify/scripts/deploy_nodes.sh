#!/bin/bash
# deploy_nodes.sh
# This script is for the non-bootstrap VMs.
# It deploys two node containers on ports 8001 and 8002.
#
# The script auto-detects the machine's IP address,
# then bind-mounts the project root (one level up from scripts/) into /app.
# Both nodes connect to the bootstrap node at IP=10.0.62.44, port=8000.

# 1) Determine the script's directory and the project root.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 2) Change to the project root directory
cd "$PROJECT_ROOT"

# 3) Detect this machine's IP address
MY_IP=$(hostname -I | awk '{print $1}')

# 4) Define ports and bootstrap info
NODE1_PORT=8001
NODE2_PORT=8002
BOOTSTRAP_IP="10.0.62.44"
BOOTSTRAP_PORT=8000

echo "Detected IP: ${MY_IP}"
echo "Using project directory: ${PROJECT_ROOT}"

# 5) Start the first node container
echo "Starting first node container on port ${NODE1_PORT}..."
docker run -d --name node1 \
  -p ${NODE1_PORT}:${NODE1_PORT} \
  -v "${PROJECT_ROOT}:/app" \
  -e IP=${MY_IP} \
  -e PORT=${NODE1_PORT} \
  -e FLASK_ENV=development \
  -e FLASK_DEBUG=1 \
  -e PYTHONUNBUFFERED=1 \
  chord-app \
  sh -c "sleep 1 && python app.py \
    --ip ${MY_IP} \
    --port ${NODE1_PORT} \
    --bootstrap_ip ${BOOTSTRAP_IP} \
    --bootstrap_port ${BOOTSTRAP_PORT}"

# 6) Wait a bit
echo "Waiting 2 seconds..."
sleep 2

# 7) Start the second node container
echo "Starting second node container on port ${NODE2_PORT}..."
docker run -d --name node2 \
  -p ${NODE2_PORT}:${NODE2_PORT} \
  -v "${PROJECT_ROOT}:/app" \
  -e IP=${MY_IP} \
  -e PORT=${NODE2_PORT} \
  -e FLASK_ENV=development \
  -e FLASK_DEBUG=1 \
  -e PYTHONUNBUFFERED=1 \
  chord-app \
  sh -c "sleep 1 && python app.py \
    --ip ${MY_IP} \
    --port ${NODE2_PORT} \
    --bootstrap_ip ${BOOTSTRAP_IP} \
    --bootstrap_port ${BOOTSTRAP_PORT}"
