# routes/data.py
import random
import time
from flask import Blueprint, request, jsonify, current_app
import hashlib
import requests
import os
import threading

insert_bp = Blueprint('data', __name__)

@insert_bp.route("/nodeinfo", methods=["GET"])
def node_info():
    node = current_app.config["NODE"]
    info = {
        "replica_store": node.replica_store,
        "id": node.id,
        "ip": node.ip,
        "port": node.port,
        #"is_bootstrap": node.is_bootstrap,
        "data_store": node.data_store,
        "replication_factor": node.replication_factor,
        "consistency_mode": node.consistency_mode,
        #"successor": node.successor,
        #"predecessor": node.predecessor,
        # Optionally, include details on pending requests if desired:
        #"pending_requests_count": len(node.pending_requests)
    }
    return jsonify(info), 200

def compute_hash(key):
    h = hashlib.sha1(key.encode('utf-8')).hexdigest()
    return int(h, 16)



@insert_bp.route("/insert", methods=["POST"])
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

    response, req_id = node.insert(key, value, origin)
    
    # The Origin Node Must Block (or otherwise wait) for the final callback
    if origin is None:
        with node.pending_requests_lock:
            pending = node.pending_requests.get(req_id)
        #print(f"insert_response called in process {os.getpid()}, node object at {hex(id(node))}, req_id={req_id}")
        if pending and pending["event"].wait(timeout=20):  # increased timeout
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
        # If not the origin node, return the response to the predecessor node
        return jsonify(response), 200


@insert_bp.route("/insert_response", methods=["POST"])
def insert_response():
    # This is the callback endpoint that the final (responsible) node calls
    # to deliver the final result to the origin node.
    node = current_app.config["NODE"]
    data = request.get_json()
    req_id = data.get("request_id")
    final_result = data.get("final_result")
    #print(f"Received insert response for request_id {req_id}")
    print(f"insert_response called in process {os.getpid()}, node object at {hex(id(node))}, req_id={req_id}")
    # if the request_id exists in the pending_requests dict of the node instance then set the result and event
    #print(f"Received insert response for request_id {req_id}")  # Debug
    if req_id in node.pending_requests:
        node.pending_requests[req_id]["result"] = final_result
        node.pending_requests[req_id]["event"].set()
        print(f"Callback processed successfully for {req_id}")  # Debug
        #print(f"Callback processed successfully for {req_id}")  # Debug
        return jsonify({"result": True, "message": "Callback received."}), 200
    else:
        print(f"Unknown request_id: {req_id}")  # Debug
        return jsonify({"result": False, "error": "Unknown request_id"}), 404
    
@insert_bp.route("/async_replicate_insert", methods=["POST"])
def async_replicate_insert():
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
    node.async_replicate_insert(key, value, replication_count)
    return jsonify({"result": True, "message": "Replication step processed."}), 200

@insert_bp.route("/chain_replicate_insert", methods=["POST"])
def chain_replicate_insert():
    """
    This endpoint receives chain replication requests. It expects a JSON payload with:
       - key: the key to replicate
       - value: the associated value
       - replication_count: the number of additional replicas to create
    """
    node = current_app.config["NODE"]
    data = request.get_json()
    key = data.get("key")
    value = data.get("value")
    replication_count = data.get("replication_count", 0)
    origin = data.get("origin")
    final_result = data.get("final_result")
    # Call the node's chain_replicate_insert method.
    node.chain_replicate_insert(key, value, replication_count, origin, final_result)
    return jsonify({"ack":True, "result": True, "message": "Chain replication step processed."}), 200

@insert_bp.route("/start_inserts", methods=["POST"])
def start_inserts():
    data = request.get_json()
    file_number = data.get("file_number", "00")  # default if missing
    file_path = f"./expirements/insert/insert_{file_number}_part.txt"
    node = current_app.config["NODE"]
    port = node.port

    # Read lines
    try:
        with open(file_path, "r") as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return jsonify({
            "status": "error",
            "message": f"File not found: {file_path}"
        }), 404

    start_time = time.time()
    # Perform the actual inserts
    for key in lines:
        # Either a direct local insert(key, value) or:
        requests.post(f"http://127.0.0.1:{port}/insert",
                      json={"key": key, "value": f"value_from_{file_number}"})
    duration = time.time() - start_time

    return jsonify({
        "status": "done",
        "inserted": len(lines),
        "time_seconds": round(duration, 2)
    }), 200
