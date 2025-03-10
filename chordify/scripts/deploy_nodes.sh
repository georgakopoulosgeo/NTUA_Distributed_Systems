#!/bin/bash
# deploy_nodes.sh
# This script is for non-bootstrap VMs.
# It automatically uses the machine's IP and deploys two nodes on ports 8001 and 8002.

# Get the machine's IP address
MY_IP=$(hostname -I | awk '{print $1}')
BOOTSTRAP_IP="10.0.62.44"
BOOTSTRAP_PORT=8000
NODE1_PORT=8001
NODE2_PORT=8002

echo "Detected IP: ${MY_IP}"

echo "Starting first node on ${MY_IP}:${NODE1_PORT}..."
docker run -d --name node1 \
  -p ${NODE1_PORT}:${NODE1_PORT} \
  -e IP=${MY_IP} -e PORT=${NODE1_PORT} \
  chord-app \
  python api.py --ip ${MY_IP} --port ${NODE1_PORT} \
  --bootstrap_ip ${BOOTSTRAP_IP} --bootstrap_port ${BOOTSTRAP_PORT}

echo "Waiting 2 seconds before starting the second node..."
sleep 2

echo "Starting second node on ${MY_IP}:${NODE2_PORT}..."
docker run -d --name node2 \
  -p ${NODE2_PORT}:${NODE2_PORT} \
  -e IP=${MY_IP} -e PORT=${NODE2_PORT} \
  chord-app \
  python api.py --ip ${MY_IP} --port ${NODE2_PORT} \
  --bootstrap_ip ${BOOTSTRAP_IP} --bootstrap_port ${BOOTSTRAP_PORT}
