from flask import Flask, request, jsonify
from node import node

app = Flask(__name__)

@app.route('/insert', methods=['POST'])
def insert():
    data = request.json
    result = node.insert(data["key"], data["value"])
    return jsonify({"message": result})

@app.route('/query', methods=['GET'])
def query():
    key = request.args.get("key")
    result = node.query(key)
    return jsonify({"result": result})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(node.port))
