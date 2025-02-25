import requests
import time

# Define the nodes in the Chord network
nodes = [
    "http://127.0.0.1:8000",  # Insert happens here!
    "http://127.0.0.1:8001",
    "http://127.0.0.1:8002",
    "http://127.0.0.1:8003",
    "http://127.0.0.1:8004",
]

key = "yolo"
value = "Imagine"

# Function to insert data into a specific node
def insert_data(node_url, key, value):
    payload = {"key": key, "value": value}
    try:
        response = requests.post(f"{node_url}/insert", json=payload, timeout=3)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# Function to query data from a specific node (local query only)
def get_data(node_url, key):
    try:
        response = requests.get(f"{node_url}/local_query", params={"key": key}, timeout=3)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# Step 1: Insert data into node 8000
print(f"🔹 Inserting '{key}: {value}' into {nodes[2]}")
insert_response = insert_data(nodes[2], key, value)
print("➡️ Insert Response:", insert_response)

# Step 2: Read immediately from all nodes (Possible Stale Reads)
time.sleep(0.01)  # Short wait before first read (simulate immediate request)
print("\n🔍 Checking for stale reads immediately after insert...\n")

for node in nodes:
    print(f"🔄 Reading '{key}' from {node} immediately...")
    response = get_data(node, key)
    print(f"📌 Response from {node}: {response}")

# Step 3: Wait 2 seconds and check again (simulate replication delay)
time.sleep(2)

print("\n⏳ Checking for eventual consistency after 2 seconds...\n")
for node in nodes:
    response = get_data(node, key)
    print(f"✅ Response from {node}: {response}")

# Step 4: Final check after full replication should have completed
time.sleep(3)

print("\n⏳ Final check after 5 seconds (should be fully consistent)...\n")
for node in nodes:
    response = get_data(node, key)
    print(f"✅ Final Response from {node}: {response}")
