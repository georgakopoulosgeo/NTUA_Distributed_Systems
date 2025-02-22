# routes/overlay.py
from flask import Blueprint, request, jsonify, current_app
import requests

overlay_bp = Blueprint('overlay', __name__)

@overlay_bp.route("/overlay", methods=["GET"])
def overlay():
    node = current_app.config['NODE']
    if node.is_bootstrap:
        ring = current_app.config.get('RING', [])
        minimal_ring = []
        for entry in ring:
            minimal_ring.append({
                "id": entry["id"],
                "ip": entry["ip"],
                "port": entry["port"],
                "predecessor": entry["predecessor"]["ip"],
                "successor": entry["successor"]["ip"]
            })
        return jsonify({"ring": minimal_ring}), 200
    else:
        try:
            bootstrap_url = f"http://{node.bootstrap_ip}:{node.bootstrap_port}/overlay"
            response = requests.get(bootstrap_url)
            if response.status_code == 200:
                return response.json(), 200
            else:
                return jsonify({"error": "Δεν ήταν δυνατή η λήψη του overlay"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500
