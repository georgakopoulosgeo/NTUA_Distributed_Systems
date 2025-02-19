from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
import time
import subprocess

load_dotenv()

BOOTSTRAP_IP = os.getenv("BOOTSTRAP_IP", "127.0.0.1")
BOOTSTRAP_PORT = int(os.getenv("BOOTSTRAP_PORT", "8000"))

app = Flask(__name__)

# Λίστα με τους ενεργούς κόμβους
active_nodes = []

@app.route('/join', methods=['POST'])
def join():
    data = request.json
    node_info = {"ip": data["ip"], "port": data["port"], "id": len(active_nodes)}
    active_nodes.append(node_info)
    return jsonify({"message": "Node joined", "node_id": node_info["id"], "nodes": active_nodes})

@app.route('/nodes', methods=['GET'])
def get_nodes():
    return jsonify(active_nodes)

NUM_NODES = int(os.getenv("TOTAL_NODES", 5))

def start_nodes():
    for i in range(NUM_NODES):
        port = 8001 + i
        cmd = f"docker run --name node{i+1} --network chord-network -e PORT={port} -e IP=0.0.0.0 --env-file .env -p {port}:{port} --rm chordify"
        print(f"Starting Node {i+1} on port {port}...")
        subprocess.Popen(cmd, shell=True)  # Runs in the background
        time.sleep(2)  # Small delay to avoid race conditions


if __name__ == "__main__":
    print(f"Bootstrap node running on {BOOTSTRAP_IP}:{BOOTSTRAP_PORT}")
    app.run(host="0.0.0.0", port=BOOTSTRAP_PORT)
    start_nodes()
