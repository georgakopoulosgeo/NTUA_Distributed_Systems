# routes/join.py
from flask import Blueprint, request, jsonify, current_app
import requests

join_bp = Blueprint('join', __name__)

@join_bp.route("/join", methods=["POST"])
def join():
    # Access the node instance from the app config
    node = current_app.config['NODE']
    if not node.is_bootstrap:
        return jsonify({"error": "Μόνο ο bootstrap κόμβος δέχεται join requests"}), 400

    data = request.get_json()
    new_node_info = {
        "ip": data.get("ip"),
        "port": data.get("port"),
        "id": data.get("id")
    }
    print(f"[Bootstrap] Node joining: {new_node_info}")

    # Fetch the current ring from app.config
    ring = current_app.config.get('RING', [])

    # Add the new node to the ring if it's not already there
    if not any(n['id'] == new_node_info['id'] for n in ring):
        ring.append(new_node_info)
    ring.sort(key=lambda n: n["id"])
    n = len(ring)

    # Find the index of the new node in the sorted ring
    new_index = ring.index(new_node_info)
    # Identify the successor and predecessor of the new node
    pred_index = (new_index - 1) % n
    succ_index = (new_index + 1) % n

    predecessor_info = ring[pred_index]
    successor_info = ring[succ_index]

    # 1) Update the new node's pointers in the ring list
    ring[new_index]["predecessor"] = {
        "ip": predecessor_info["ip"],
        "port": predecessor_info["port"],
        "id": predecessor_info["id"]
    }
    ring[new_index]["successor"] = {
        "ip": successor_info["ip"],
        "port": successor_info["port"],
        "id": successor_info["id"]
    }

    # 2) Update the predecessor so its successor is the new node
    ring[pred_index]["successor"] = {
        "ip": new_node_info["ip"],
        "port": new_node_info["port"],
        "id": new_node_info["id"]
    }
    try:
        url = f"http://{predecessor_info['ip']}:{predecessor_info['port']}/update_neighbors"
        payload = {
            "successor": ring[pred_index]["successor"],
            "predecessor": predecessor_info.get("predecessor", {})
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[Bootstrap] Failed to update predecessor {predecessor_info}: {e}")

    # 3) Update the successor so its predecessor is the new node
    ring[succ_index]["predecessor"] = {
        "ip": new_node_info["ip"],
        "port": new_node_info["port"],
        "id": new_node_info["id"]
    }
    try:
        url = f"http://{successor_info['ip']}:{successor_info['port']}/update_neighbors"
        payload = {
            "successor": successor_info.get("successor", {}),
            "predecessor": ring[succ_index]["predecessor"]
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[Bootstrap] Failed to update successor {successor_info}: {e}")

    # Store the updated ring
    current_app.config['RING'] = ring

    # Return the new node's own successor/predecessor in the response
    return jsonify({
        "message": "Node joined successfully (minimal push)",
        "successor": ring[new_index]["successor"],
        "predecessor": ring[new_index]["predecessor"],
        "ring": ring  # For debugging
    }), 200

@join_bp.route("/update_neighbors", methods=["POST"])
def update_neighbors():
    node = current_app.config['NODE']
    data = request.get_json()
    new_successor = data.get("successor")
    new_predecessor = data.get("predecessor")
    print(f"[{node.ip}:{node.port}] Ενημέρωση γειτόνων: successor={new_successor}, predecessor={new_predecessor}")
    node.update_neighbors(new_successor, new_predecessor)
    return jsonify({"message": "Neighbors updated successfully"}), 200

@join_bp.route("/get_neighbors", methods=["GET"])
def get_neighbors():
    # Optional endpoint so a node can pull its neighbor info if needed.
    node = current_app.config['NODE']
    ring = current_app.config.get('RING', [])
    for entry in ring:
        if entry["id"] == node.id:
            return jsonify({
                "successor": entry.get("successor"),
                "predecessor": entry.get("predecessor")
            }), 200
    return jsonify({"error": "Node not found in ring"}), 404
