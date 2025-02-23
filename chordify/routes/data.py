# routes/data.py
from flask import Blueprint, request, jsonify, current_app
import hashlib
import requests

data_bp = Blueprint('data', __name__)

def compute_hash(key):
    h = hashlib.sha1(key.encode('utf-8')).hexdigest()
    return int(h, 16)

@data_bp.route("/insert", methods=["POST"])
def insert():
    node = current_app.config["NODE"]
    data = request.get_json()
    key = data.get("key")
    value = data.get("value")

    # Call the node.insert() method which now returns a dictionary
    response = node.insert(key, value)

    # You can decide whether to return 200 or 4xx based on "result"
    if response.get("result") is True:
        return jsonify(response), 200
    else:
        # e.g. if there's an error or the key was not inserted
        return jsonify(response), 404

# some pheudocode by me
@data_bp.route("/query", methods=["GET"])
def query():
    node = current_app.config['NODE']
    key = request.args.get("key")  # Extract the key from query parameters
    
    if not key:
        return jsonify({"error": "Missing key parameter"}), 400
    print(f"Node {node.ip}:{node.port} querying for key '{key}', successor: {node.successor}")
    result = node.query(key)
    
    if result is not None:
        key_hash = compute_hash(key)
        print(f"[{node.ip}:{node.port}] Query request for key '{key}' (hash: {key_hash}).")
        return jsonify({"key": key, "result": result}), 200
    else:
        return jsonify({"error": "Key - Song not found"}), 404
    
@data_bp.route("/query_all", methods=["POST"])
def query_all():
    node = current_app.config['NODE']
    data = request.get_json()
    origin = data.get("origin")
    aggregated_data = data.get("aggregated_data", {})
    
    # Ενημέρωση με τα τοπικά δεδομένα του κόμβου
    aggregated_data.update(node.data_store)
    
    successor_ip = node.successor.get("ip")
    successor_port = node.successor.get("port")
    successor_identifier = f"{successor_ip}:{successor_port}"
    
    # Ελέγχουμε αν ο επόμενος κόμβος είναι ο κόμβος εκκίνησης
    if successor_identifier == origin:
        return jsonify({"value": aggregated_data}), 200
    else:
        url = f"http://{successor_ip}:{successor_port}/query_all"
        payload = {
            "origin": origin,
            "aggregated_data": aggregated_data
        }
        try:
            print(f"[{node.ip}:{node.port}] Προώθηση wildcard query '*' στον successor {successor_identifier}.")
            response = requests.get(url, json=payload)
            return response.json()
        except Exception as e:
            return jsonify({"error": str(e), "value": aggregated_data}), 500

    


@data_bp.route("/delete", methods=["POST"])
def delete():
    node = current_app.config['NODE']
    data = request.get_json()
    key = data.get("key")
    # node.delete(key) returns a dict with "result", "ip", etc.
    response_data = node.delete(key)

    if response_data.get("result") is True:
        return jsonify(response_data), 200
    else:
        return jsonify(response_data), 404
