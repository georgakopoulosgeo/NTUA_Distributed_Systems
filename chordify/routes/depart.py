# routes/depart.py
from flask import Blueprint, request, jsonify, current_app
import threading, time, os
import requests

depart_bp = Blueprint('depart', __name__)

def serialize_node_info(n):
    return {"id": n["id"], "ip": n["ip"], "port": n["port"]}

@depart_bp.route("/remove_node", methods=["POST"])
def remove_node():
    node = current_app.config['NODE']
    if not node.is_bootstrap:
        return jsonify({"error": "Only bootstrap can remove a node from ring"}), 400

    data = request.get_json()
    rm_id = data.get("id")
    rm_ip = data.get("ip")
    rm_port = data.get("port")
    print(f"[Bootstrap] Removing node: {rm_ip}:{rm_port} (id={rm_id})")

    ring = current_app.config.get('RING', [])
    ring = [n for n in ring if n["id"] != rm_id]
    current_app.config['RING'] = ring  # update the ring

    # Recalculate pointers
    if ring:
        ring.sort(key=lambda n: n["id"])
        new_ring = []
        n = len(ring)
        for i in range(n):
            succ = ring[(i + 1) % n]
            pred = ring[(i - 1) % n]
            new_ring.append({
                "id": ring[i]["id"],
                "ip": ring[i]["ip"],
                "port": ring[i]["port"],
                "successor": serialize_node_info(succ),
                "predecessor": serialize_node_info(pred)
            })
        current_app.config['RING'] = new_ring
        for n_info in new_ring:
            print(f"  Node {n_info['ip']}:{n_info['port']} (id={n_info['id']}) -> predecessor: {n_info['predecessor']['id']}, successor: {n_info['successor']['id']}")
    else:
        print("[Bootstrap] Ring is empty.")

    return jsonify({"message": "Node removed from ring", "ring": current_app.config['RING']}), 200

@depart_bp.route("/depart", methods=["POST"])
def depart():
    node = current_app.config['NODE']
    if node.is_bootstrap:
        return jsonify({"error": "Bootstrap does not depart"}), 400
    else:
        success = node.depart()
        if success:
            def shutdown_after_delay():
                time.sleep(1)
                os._exit(0)
            threading.Thread(target=shutdown_after_delay).start()
            return jsonify({"message": "Node departed gracefully"}), 200
        else:
            return jsonify({"error": "Depart failed"}), 500
