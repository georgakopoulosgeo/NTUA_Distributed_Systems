# routes/data.py
from flask import Blueprint, request, jsonify, current_app
import hashlib
import requests
import threading

data_bp = Blueprint('data', __name__)

@data_bp.route("/nodeinfo", methods=["GET"])
def node_info():
    node = current_app.config["NODE"]
    info = {
        "replica_store": node.replica_store,
        "id": node.id,
        #"ip": node.ip,
        #"port": node.port,
        #"is_bootstrap": node.is_bootstrap,
        "data_store": node.data_store,
        #"successor": node.successor,
        #"predecessor": node.predecessor,
        # Optionally, include details on pending requests if desired:
        #"pending_requests_count": len(node.pending_requests)
    }
    return jsonify(info), 200

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
        print(f"Pending Requests: {node.pending_requests}")  # Debug line
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
        print(f"Callback processed successfully for {req_id}")  # Debug
        return jsonify({"result": True, "message": "Callback received."}), 200
    else:
        print(f"Unknown request_id: {req_id}")  # Debug
        return jsonify({"result": False, "error": "Unknown request_id"}), 404
    
@data_bp.route("/replicate_insert", methods=["POST"])
def replicate_insert():
    """
    This endpoint receives replication requests. It expects a JSON payload with:
       - key: the key to replicate
       - value: the associated value
       - replication_count: the number of additional replicas to create
    """
    node = current_app.config["NODE"]
    data = request.get_json()
    key = data.get("key")
    value = data.get("value")
    replication_count = data.get("replication_count", 0)
    # Call the node's replicate_insert method.
    node.replicate_insert(key, value, replication_count)
    return jsonify({"result": True, "message": "Replication step processed."}), 200



@data_bp.route("/query", methods=["GET"])
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


@data_bp.route("/query_response", methods=["POST"])
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
    
@data_bp.route("/local_query", methods=["GET"])
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

    

@data_bp.route("/delete", methods=["POST"])
def delete():
    node = current_app.config["NODE"]
    data = request.get_json()
    key = data.get("key")
    origin = data.get("origin")  # might be None if this is the original client call

    response = node.delete(key, origin)

    if origin is None:
        # This means we are the origin node
        # The node.delete() method has created a request_id
        # Let's get the last one from pending_requests (or store it more carefully)
        req_id = list(node.pending_requests.keys())[-1]
        pending = node.pending_requests[req_id]

        # Wait for up to 3 seconds for the responsible node to callback
        if pending["event"].wait(timeout=3):
            final_result = pending["result"]
            # Clean up
            del node.pending_requests[req_id]
            # Return the final result to the client
            if final_result.get("result") is True:
                return jsonify(final_result), 200
            else:
                return jsonify(final_result), 404
        else:
            # Timeout: no callback arrived
            del node.pending_requests[req_id]
            return jsonify({"result": False, "error": "Timeout waiting for delete callback"}), 504
    else:
        # If origin is not None, we are a forwarding or responsible node
        # Return whatever the node.delete() returned
        return jsonify(response), 200


@data_bp.route("/delete_response", methods=["POST"])
def delete_response():
    # Get the current node instance from the Flask app configuration.
    node = current_app.config["NODE"]
    data = request.get_json()
    req_id = data.get("request_id")
    final_result = data.get("final_result")

    # Check if the request_id exists in the pending_requests dictionary.
    # If it does, set the result and signal the threading event.
    # Else, return a 404 error.
    if req_id in node.pending_requests:
        node.pending_requests[req_id]["result"] = final_result
        node.pending_requests[req_id]["event"].set()
        return jsonify({"result": True, "message": "Delete callback received."}), 200
    else:
        return jsonify({"result": False, "error": "Unknown request_id"}), 404
    

@data_bp.route("/replicate_delete", methods=["POST"])
def replicate_delete_route():
    """
    This endpoint receives replication delete requests.
    It expects a JSON payload with:
       - key: the key to delete from replica_store
       - replication_count: the number of additional replica deletions to propagate
    """
    node = current_app.config["NODE"]
    data = request.get_json()
    key = data.get("key")
    replication_count = data.get("replication_count", 0)
    node.replicate_delete(key, replication_count)
    return jsonify({"result": True, "message": "Replication delete step processed."}), 200