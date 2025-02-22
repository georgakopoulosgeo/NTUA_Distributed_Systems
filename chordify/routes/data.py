# routes/data.py
from flask import Blueprint, request, jsonify, current_app
import hashlib

data_bp = Blueprint('data', __name__)

def compute_hash(key):
    h = hashlib.sha1(key.encode('utf-8')).hexdigest()
    return int(h, 16)

@data_bp.route("/insert", methods=["POST"])
def insert():
    node = current_app.config['NODE']
    data = request.get_json()
    key = data.get("key")
    value = data.get("value")
    result = node.insert(key, value)
    key_hash = compute_hash(key)
    print(f"[{node.ip}:{node.port}] Αίτημα insert για το key '{key}' (hash: {key_hash}).")
    return jsonify({"result": result, "data_store": node.data_store}), 200

@data_bp.route("/query/<key>", methods=["GET"])
def query(key):
    node = current_app.config['NODE']
    value = node.query(key)
    if value is not None:
        return jsonify({"key": key, "value": value}), 200
    else:
        return jsonify({"error": "Το key δεν βρέθηκε"}), 404

@data_bp.route("/delete", methods=["POST"])
def delete():
    node = current_app.config['NODE']
    data = request.get_json()
    key = data.get("key")
    result = node.delete(key)
    if result:
        return jsonify({"result": True}), 200
    else:
        return jsonify({"error": "Το key δεν βρέθηκε"}), 404
