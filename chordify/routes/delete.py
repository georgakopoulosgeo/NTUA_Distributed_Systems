from flask import Blueprint, request, jsonify, current_app
import hashlib
import requests
import threading

delete_bp = Blueprint('delete', __name__)

@delete_bp.route("/delete", methods=["POST"])
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


@delete_bp.route("/delete_response", methods=["POST"])
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
    

@delete_bp.route("/replicate_delete", methods=["POST"])
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