import hashlib
import requests
import os
from dotenv import load_dotenv

load_dotenv()

class ChordNode:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = int(port)
        self.node_id = self.hash_function(f"{ip}:{port}")
        self.data_store = {}
        self.successor = None
        self.predecessor = None

    def hash_function(self, key):
        return int(hashlib.sha1(key.encode()).hexdigest(), 16) % (2**160)

    def insert(self, key, value):
        key_hash = self.hash_function(key)
        if self.is_responsible_for_key(key_hash):
            self.data_store[key_hash] = value
            return f"Inserted {key}: {value} at node {self.node_id}"
        return self.forward_request("/insert", {"key": key, "value": value})

    def query(self, key):
        key_hash = self.hash_function(key)
        if key_hash in self.data_store:
            return self.data_store[key_hash]
        return self.forward_request("/query", {"key": key})

    def forward_request(self, endpoint, data):
        if self.successor:
            url = f"http://{self.successor['ip']}:{self.successor['port']}{endpoint}"
            response = requests.post(url, json=data)
            return response.json()
        return "No successor available"

    def is_responsible_for_key(self, key_hash):
        if not self.successor:
            return True
        return self.node_id <= key_hash < self.successor["id"]

    def join_network(self):
        bootstrap_ip = os.getenv("BOOTSTRAP_IP")
        bootstrap_port = os.getenv("BOOTSTRAP_PORT")
        response = requests.post(f"http://{bootstrap_ip}:{bootstrap_port}/join", json={"ip": self.ip, "port": self.port})
        data = response.json()
        print(f"Joined network with ID {data['node_id']}")

NODE_IP = os.getenv("NODE_IP", "127.0.0.1")
NODE_PORT = os.getenv("NODE_PORT", "8001")

node = ChordNode(NODE_IP, NODE_PORT)
node.join_network()