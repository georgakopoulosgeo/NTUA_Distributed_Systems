import threading
import requests
import time
import random

def get_overlay(node_addr):
    """Call /overlay on the given node and return the JSON response."""
    url = f"http://{node_addr}/overlay"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()  # e.g. { "ring": [ ... ] }

def insert_from_file(node_addr, file_path):
    """Reads a file and inserts each key-value pair to the given node."""
    try:
        with open(file_path, 'r') as f:
            keys = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"File {file_path} not found for node {node_addr}.")
        return

    start = time.time()
    for key in keys:
        value = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5))
        payload = {"key": key, "value": value}
        url = f"http://{node_addr}/insert"
        try:
            r = requests.post(url, json=payload)
            r.raise_for_status()
        except Exception as e:
            print(f"Error inserting {key} on {node_addr}: {e}")
    end = time.time()
    print(f"[{node_addr}] Inserted {len(keys)} keys from {file_path} in {end - start:.2f} seconds.")

def run_insert_experiment(overlay_node_addr, num_nodes=5):
    """
    1) Gets the overlay (which returns a dict: { "ring": [ {id, entryIp, port, ...}, ... ] }).
    2) Sorts the ring entries by their 'id' (or any other consistent field).
    3) Spawns threads for up to num_nodes entries.
    4) Each thread reads from insert_XX_part.txt, where XX matches the index in the sorted ring.
    """
    overlay_info = get_overlay(overlay_node_addr)
    ring = overlay_info.get("ring", [])

    if len(ring) < num_nodes:
        print(f"Overlay does not contain {num_nodes} nodes. Aborting experiment.")
        return

    # Sort ring by node 'id' or any consistent criterion
    # If 'id' is not numeric, you might need a different sort key.
    ring = sorted(ring, key=lambda x: x["id"])

    threads = []

    # For each node, pick the file "insert_XX_part.txt"
    for i, entry in enumerate(ring[:num_nodes]):
        node_id = entry["id"]           # e.g. "node0", or "some_hash_id"
        node_ip = entry["ip"]      # e.g. "192.168.1.2"
        node_port = entry["port"]       # e.g. "8001"
        node_addr = f"{node_ip}:{node_port}"

        file_name = f"./insert/insert_{i:02d}_part.txt"
        # If you specifically want to match by node_id,
        # you could do something like:
        #   file_name = f"insert_{node_id}_part.txt"
        # but typically it's easier to map by index i.

        t = threading.Thread(target=insert_from_file, args=(node_addr, file_name))
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    print(f"Insert experiment completed for {num_nodes} nodes.")

# For quick testing:
if __name__ == "__main__":
    run_insert_experiment("127.0.0.1:8000", num_nodes=5)
