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

    # Here you can call a shared function to update the ring (which might be refactored into a separate module)
    # For simplicity, assume you have a global 'ring' managed by the bootstrap node.
    ring = current_app.config.get('RING', [])
    if not any(n['id'] == new_node_info['id'] for n in ring):
        ring.append(new_node_info)
    # (Re)calculate pointers here...
    # Broadcast new pointers, etc.
    ring.sort(key=lambda n: n["id"])
    n = len(ring)
    for i in range(n):
        successor = ring[(i + 1) % n]
        predecessor = ring[(i - 1) % n]
        ring[i]["successor"] = {"ip": successor["ip"], "port": successor["port"], "id": successor["id"]}
        ring[i]["predecessor"] = {"ip": predecessor["ip"], "port": predecessor["port"], "id": predecessor["id"]}

    # Broadcast: Ενημέρωση όλων των κόμβων στο ring για τους νέους pointers
    for n_info in ring:
        # Αν ο κόμβος είναι ο bootstrap, ενημέρωσε το τοπικό node object
        if n_info["ip"] == node.ip and n_info["port"] == node.port:
            node.update_neighbors(n_info["successor"], n_info["predecessor"])
        else:
            try:
                url = f"http://{n_info['ip']}:{n_info['port']}/update_neighbors"
                #url = f"http://localhost:{n_info['port']}/update_neighbors"
                payload = {
                    "successor": n_info["successor"],
                    "predecessor": n_info["predecessor"]
                }
                requests.post(url, json=payload)
            except Exception as e:
                print(f"[Bootstrap] Σφάλμα κατά την ενημέρωση του κόμβου {n_info}: {e}")

    # Write ring back to app.config
    current_app.config['RING'] = ring

    # Finally, return the pointers for the joining node
    for entry in ring:
        if entry["id"] == new_node_info["id"]:
            return jsonify({
                "message": "Επιτυχής ένταξη",
                "successor": entry.get("successor"),
                "predecessor": entry.get("predecessor"),
                "ring": ring  # Optional debugging info
            }), 200
    return jsonify({"error": "Ο νέος κόμβος δεν βρέθηκε στο ring"}), 500

@join_bp.route("/update_neighbors", methods=["POST"])
def update_neighbors():
    node = current_app.config['NODE']
    data = request.get_json()
    new_successor = data.get("successor")
    new_predecessor = data.get("predecessor")
    print(f"[{node.ip}:{node.port}] Ενημέρωση γειτόνων: successor={new_successor}, predecessor={new_predecessor}")
    node.update_neighbors(new_successor, new_predecessor)
    return jsonify({"message": "Neighbors updated successfully"}), 200
