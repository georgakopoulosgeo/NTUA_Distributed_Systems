from flask import Blueprint, request, jsonify, current_app
import hashlib
import requests
import threading

query_bp = Blueprint('query', __name__)

@query_bp.route("/query", methods=["GET"])
def query():
    node = current_app.config['NODE']
    key = request.args.get("key")  # Extract the key from query parameters
    origin_ip = request.args.get("origin_ip")
    origin_port = request.args.get("origin_port")
    request_id = request.args.get("request_id")
    origin = None
    if origin_ip and origin_port and request_id:
        origin = {"ip": origin_ip, "port": origin_port, "request_id": request_id}
        
    if not key:
        return jsonify({"error": "Missing key parameter"}), 400

    if key == "*":  # Wildcard query remains unchanged
        print(f"Node {node.ip}:{node.port} querying for ALL keys (wildcard '*').")
        all_songs = node.query_wildcard(origin=f"{node.ip}:{node.port}")
        return jsonify({"all_songs": all_songs}), 200

    result = node.query(key, origin)

    # If this node is the original requester, wait for the query callback.
    if origin is None:
        req_id = list(node.pending_requests.keys())[-1]
        pending = node.pending_requests[req_id]
        if pending["event"].wait(timeout=3):  # Wait up to 3 seconds
            final_result = pending["result"]
            del node.pending_requests[req_id]
            return jsonify(final_result), 200
        else:
            del node.pending_requests[req_id]
            return jsonify({"result": False, "error": "Timeout waiting for final node callback"}), 504
    else:
        # If this request was forwarded, return the immediate response.
        return jsonify(result), 200


@query_bp.route("/query_response", methods=["POST"])
def query_response():
    node = current_app.config["NODE"]
    data = request.get_json()
    req_id = data.get("request_id")
    final_result = data.get("final_result")
    print(f"Received query response for request_id {req_id}")
    
    if req_id in node.pending_requests:
        node.pending_requests[req_id]["result"] = final_result
        node.pending_requests[req_id]["event"].set()
        return jsonify({"result": True, "message": "Query callback received."}), 200
    else:
        return jsonify({"result": False, "error": "Unknown request_id"}), 404
    
@query_bp.route("/local_query", methods=["GET"])
def local_query():
    """
    Retrieve a key's value ONLY from the local node (without forwarding).
    """
    node = current_app.config["NODE"]
    key = request.args.get("key")  # Extract the key from query parameters

    if not key:
        return jsonify({"error": "Missing key parameter"}), 400

    # Check only the local data store
    if key in node.data_store:
        return jsonify({"result": True, "value": node.data_store[key], "source": "local_store"}), 200
    elif key in node.replica_store:
        return jsonify({"result": True, "value": node.replica_store[key], "source": "replica_store"}), 200
    else:
        return jsonify({"error": "Key not found", "source": "none"}), 404