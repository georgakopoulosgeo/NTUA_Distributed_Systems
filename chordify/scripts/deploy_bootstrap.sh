#!/bin/bash
# deploy_bootstrap.sh
# This script is for the bootstrap VM.
# It automatically uses the machine's IP and deploys:
# - A bootstrap container on port 8000.
# - A second node container on port 8001.

# Get the machine's IP address (assumes the primary IP is the first in the list)
MY_IP=$(hostname -I | awk '{print $1}')
BOOTSTRAP_IP=${MY_IP}  # This should match 10.0.62.44 for the bootstrap machine.
BOOTSTRAP_PORT=8000
SECOND_NODE_PORT=8001

echo "Detected IP: ${MY_IP}"
echo "Starting bootstrap node on ${BOOTSTRAP_IP}:${BOOTSTRAP_PORT}..."
docker run -d --name bootstrap \
  -p ${BOOTSTRAP_PORT}:${BOOTSTRAP_PORT} \
  -e IP=${BOOTSTRAP_IP} -e PORT=${BOOTSTRAP_PORT} \
  chord-app \
  python api.py --ip ${BOOTSTRAP_IP} --port ${BOOTSTRAP_PORT} --bootstrap

echo "Waiting 2 seconds before starting the second node..."
sleep 2

echo "Starting second node on ${MY_IP}:${SECOND_NODE_PORT}..."
docker run -d --name node1 \
  -p ${SECOND_NODE_PORT}:${SECOND_NODE_PORT} \
  -e IP=${MY_IP} -e PORT=${SECOND_NODE_PORT} \
  chord-app \
  python api.py --ip ${MY_IP} --port ${SECOND_NODE_PORT} \
  --bootstrap_ip ${BOOTSTRAP_IP} --bootstrap_port ${BOOTSTRAP_PORT}
