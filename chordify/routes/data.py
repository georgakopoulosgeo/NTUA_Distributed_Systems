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
    '''
    When a client calls a node’s /insert endpoint (with no "origin" field in the JSON), that node (the “origin node”) will either 
    handle the insert itself (if it is responsible for that key) or forward it around the ring. Then, once the responsible node actually 
    inserts the key, it sends a callback directly back to the origin node, so that the origin node can finally return the final result to the client.
    '''
    node = current_app.config["NODE"]
    data = request.get_json()
    key = data.get("key")
    value = data.get("value")
    origin = data.get("origin")  # might be None or might exist

    response = node.insert(key, value, origin)
    
    # The Origin Node Must Block (or otherwise wait) for the final callback
    if origin is None:
        # Origin Node sets up a “pending request” so that it can block the HTTP response until the final result arrives from the responsible node.
        req_id = list(node.pending_requests.keys())[-1]
        pending = node.pending_requests[req_id]
        if pending["event"].wait(timeout=3):  # 3-second wait
            # The final result should be in the pending dict
            final_result = pending["result"]
            # cleanup
            del node.pending_requests[req_id]
            return jsonify(final_result), 200
        else:
            # Timeout
            del node.pending_requests[req_id]
            return jsonify({"result": False, "error": "Timeout waiting for final node callback"}), 504
    else:
        # If not the origin node, return the response to the predecessor node
        return jsonify(response), 200


@data_bp.route("/insert_response", methods=["POST"])
def insert_response():
    # This is the callback endpoint that the final (responsible) node calls
    # to deliver the final result to the origin node.
    node = current_app.config["NODE"]
    data = request.get_json()
    req_id = data.get("request_id")
    final_result = data.get("final_result")
    print(f"Received insert response for request_id {req_id}")

    # if the request_id exists in the pending_requests dict of the node instance then set the result and event
    if req_id in node.pending_requests:
        node.pending_requests[req_id]["result"] = final_result
        node.pending_requests[req_id]["event"].set()
        return jsonify({"result": True, "message": "Callback received."}), 200
    else:
        return jsonify({"result": False, "error": "Unknown request_id"}), 404


@data_bp.route("/query", methods=["GET"])
def query():
    node = current_app.config['NODE']
    key = request.args.get("key")  # Extract the key from query parameters
    
    if not key:
        return jsonify({"error": "Missing key parameter"}), 400

    if key == "*":  # Wildcard query
        print(f"Node {node.ip}:{node.port} querying for ALL keys (wildcard '*').")
        all_songs = node.query_wildcard(origin=f"{node.ip}:{node.port}")  # Pass origin to stop looping
        return jsonify({"all_songs": all_songs}), 200

    print(f"Node {node.ip}:{node.port} querying for key '{key}', successor: {node.successor}")
    result = node.query(key)

    if result is not None:
        key_hash = compute_hash(key)
        print(f"[{node.ip}:{node.port}] Query request for key '{key}' (hash: {key_hash}).")
        return jsonify({"key": key, "result": result}), 200
    else:
        return jsonify({"error": "Key - Song not found"}), 404
    

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
