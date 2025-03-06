from flask import Blueprint, request, jsonify, current_app
import threading
import requests

delete_bp = Blueprint('delete', __name__)

@delete_bp.route("/delete", methods=["POST"])
def delete():
    """
    Endpoint for initiating a delete request.
    The origin node sets up a pending request and waits for a callback.
    """
    node = current_app.config["NODE"]
    data = request.get_json()
    key = data.get("key")
    origin = data.get("origin")  # may be None or provided

    response = node.delete(key, origin)
    
    if origin is None:
        # The origin node waits for the callback with the final result.
        req_id = list(node.pending_requests.keys())[-1]
        pending = node.pending_requests[req_id]
        if pending["event"].wait(timeout=3):  # Wait up to 3 seconds
            final_result = pending["result"]
            del node.pending_requests[req_id]
            return jsonify(final_result), 200
        else:
            del node.pending_requests[req_id]
            return jsonify({"result": False, "error": "Timeout waiting for deletion callback"}), 504
    else:
        return jsonify(response), 200


@delete_bp.route("/delete_response", methods=["POST"])
def delete_response():
    """
    Callback endpoint that receives the final deletion result at the origin node.
    """
    node = current_app.config["NODE"]
    data = request.get_json()
    req_id = data.get("request_id")
    final_result = data.get("final_result")
    print(f"Received delete response for request_id {req_id}")

# if the request_id exists in the pending_requests dict of the node instance then set the result and event
    if req_id in node.pending_requests:
        node.pending_requests[req_id]["result"] = final_result
        node.pending_requests[req_id]["event"].set()
        print(f"Delete callback processed successfully for {req_id}")
        return jsonify({"result": True, "message": "Callback received."}), 200
    else:
        print(f"Unknown request_id: {req_id}")
        return jsonify({"result": False, "error": "Unknown request_id"}), 404


@delete_bp.route("/async_replicate_delete", methods=["POST"])
def async_replicate_delete():
    """
    Endpoint for receiving asynchronous deletion replication requests.
    """
    node = current_app.config["NODE"]
    data = request.get_json()
    key = data.get("key")
    replication_count = data.get("replication_count", 0)
    node.async_replicate_delete(key, replication_count)
    return jsonify({"result": True, "message": "Async deletion replication processed."}), 200


@delete_bp.route("/chain_replicate_delete", methods=["POST"])
def chain_replicate_delete():
    """
    Endpoint for receiving chain deletion replication requests.
    """
    node = current_app.config["NODE"]
    data = request.get_json()
    key = data.get("key")
    replication_count = data.get("replication_count", 0)
    node.chain_replicate_delete(key, replication_count)
    return jsonify({"ack": True, "result": True, "message": "Chain deletion replication step processed."}), 200
