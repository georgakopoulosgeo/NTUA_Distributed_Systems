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

@depart_bp.route("/absorb_keys", methods=["POST"])
def absorb_keys():
    """
    This endpoint is called by a departing node so that its successor can absorb
    the keys for which the departing node was primary.
    The successor adds these keys to its own data_store and re-initiates the replication
    process to rebuild the replication chain correctly. That replication chain will also
    ensure that any stale replicas (from nodes further in the old chain) are removed.
    """
    node = current_app.config['NODE']
    data = request.get_json()
    keys = data.get("keys", {})
    replication_factor = data.get("replication_factor", 3)
    ring = current_app.config.get('RING', [])
    # Update local pointers so that node.successor is up-to-date.
    if ring:
        node.update_local_pointers(ring)
    
    # For each key from the departing node:
    for key, value in keys.items():
        # Add the key to the successor's data_store.
        node.data_store[key] = value
        # Re-establish the replication chain:
        # The successor becomes the new primary for these keys.
        # Initiate replication so that the new chain becomes:
        # primary -> successor -> next node ... (with last node cleaning up stale replicas)
        node.async_replicate_insert(key, value, replication_factor - 1)
    
    print(f"[{node.ip}:{node.port}] Absorbed keys from departing node: {list(keys.keys())}")
    return jsonify({"message": "Keys absorbed and replication updated."}), 200

@depart_bp.route("/cleanup_replicas_all", methods=["POST"])
def cleanup_replicas_all():
    node = current_app.config['NODE']
    data = request.get_json()
    ring = data.get("ring")
    replication_factor = data.get("replication_factor")
    node.cleanup_replicas(ring, replication_factor)
    return jsonify({"message": "Replica cleanup completed."}), 200

@depart_bp.route("/repair_replicas_all", methods=["POST"])
def repair_replicas_all():
    node = current_app.config['NODE']
    data = request.get_json()
    ring = data.get("ring")
    replication_factor = data.get("replication_factor")
    node.update_local_pointers(ring)
    node.repair_replicas(ring, replication_factor)
    return jsonify({"message": "Replica repair completed."}), 200

