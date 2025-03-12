from flask import Blueprint, request, jsonify, current_app
import hashlib
import requests
import threading
import os
import time

query_bp = Blueprint('query', __name__)

@query_bp.route("/query", methods=["GET"])
def query():
    node = current_app.config['NODE']
    key = request.args.get("key")  # Extract the key from query parameters
    origin_ip = request.args.get("origin_ip")
    origin_port = request.args.get("origin_port")
    request_id = request.args.get("request_id")
    chain_count_param = request.args.get("chain_count")
    chain_count = int(chain_count_param) if chain_count_param else None

    origin = None
    if origin_ip and origin_port and request_id:
        origin = {"ip": origin_ip, "port": origin_port, "request_id": request_id}
        
    if not key:
        return jsonify({"error": "Missing key parameter"}), 400

    # --- Wildcard Query Handling ---
    if key == "*":
        # For wildcard queries, use a single 'origin' parameter (ip:port) to track the initiator.
        origin = request.args.get("origin")
        if not origin:
            origin = f"{node.ip}:{node.port}"
        all_node_songs = node.query_wildcard(origin)
        # Optionally, compute the total number of songs across nodes.
        total_songs = sum(len(songs) for songs in all_node_songs.values())
        return jsonify({
            "all_songs": all_node_songs,
            "songs_count": total_songs,
            "nodes_count": len(all_node_songs)
        }), 200

    result , req_id = node.query(key, origin, chain_count)

    # If this node is the original requester, wait for the query callback.
    if origin is None:
        # Wait on the event for the specific pending request.
        with node.pending_requests_lock:
            pending = node.pending_requests.get(req_id)
        if pending and pending["event"].wait(timeout=3):
            final_result = pending["result"]
            with node.pending_requests_lock:
                del node.pending_requests[req_id]
            return jsonify(final_result), 200
        else:
            with node.pending_requests_lock:
                if req_id in node.pending_requests:
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

@query_bp.route("/start_queries", methods=["POST"])
def start_queries():
    data = request.get_json()
    file_number = data.get("file_number", "00")  # default file_number if not provided
    file_path = f"./expirements/queries/query_{file_number}.txt"

    node = current_app.config["NODE"]
    port = node.port

    # Read query keys from the file
    try:
        with open(file_path, "r") as f:
            keys = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return jsonify({
            "status": "error",
            "message": f"File not found: {file_path}"
        }), 404

    start_time = time.time()
    results = []
    # For each query key, perform the query using the node’s own /query (or /local_query) endpoint.
    for key in keys:
        try:
            # Here we call the query endpoint locally on the same node.
            # Adjust the endpoint path if needed (for example, it might be /local_query).
            response = requests.get(f"http://127.0.0.1:{port}/query?key={key}")
            response.raise_for_status()
            result = response.json()
            results.append({"key": key, "result": result})
        except Exception as e:
            results.append({"key": key, "error": str(e)})
    duration = time.time() - start_time
    throughput = len(keys) / duration if duration > 0 else 0
    return jsonify({
        "status": "done",
        "queried": len(keys),
        "time_seconds": round(duration, 2),
        "throughput": round(throughput, 2),  # new field for read throughput
        "results": results
    }), 200