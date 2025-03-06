import requests
import threading
import time

def get_overlay(bootstrap_addr):
    url = f"http://{bootstrap_addr}/overlay"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def _start_inserts_on_node(node_addr, file_number, results, index):
    """
    Thread worker function that:
      1. POSTs /start_inserts to the node_addr
      2. Passes {"file_number": file_number} as JSON
      3. Stores the response (or any error) in results[index]
    """
    url = f"http://{node_addr}/start_inserts"
    payload = {"file_number": file_number}
    start_time = time.time()

    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()  # e.g. {"status":"done","inserted":..., "time_seconds":...}
        end_time = time.time()
        total_duration = end_time - start_time

        results[index] = {
            "node": node_addr,
            "file_number": file_number,
            "node_response": data,
            "request_duration": round(total_duration, 2)
        }
    except Exception as e:
        end_time = time.time()
        results[index] = {
            "node": node_addr,
            "file_number": file_number,
            "error": str(e),
            "request_duration": round(end_time - start_time, 2)
        }

def run_distributed_insert_experiment(bootstrap_addr, num_nodes=5):
    """
    1) Fetches the overlay from bootstrap_addr
    2) Sorts the ring by 'id' (or any consistent key)
    3) Spawns threads for the first 'num_nodes' in the ring
    4) Sends each node a "file_number" = i in two-digit format ("00","01",...)
    5) Waits for all threads and prints results
    """
    overlay_data = get_overlay(bootstrap_addr)
    ring = overlay_data.get("ring", [])

    if len(ring) < num_nodes:
        print(f"Overlay only has {len(ring)} nodes, but we need {num_nodes}. Aborting.")
        return

    # Sort the ring entries by node ID (adjust if 'id' is not numeric)
    ring = sorted(ring, key=lambda x: x["id"])

    threads = []
    results = [None] * num_nodes

    # For each node, create a thread that calls /start_inserts
    for i, entry in enumerate(ring[:num_nodes]):
        #node_ip = entry["ip"]   # e.g. "node1" or "127.0.0.1"
        node_ip = "127.0.0.1"
        node_port = entry["port"]    # e.g. "8001"
        node_addr = f"{node_ip}:{node_port}"

        # Build the file_number in two-digit format, e.g. 0 -> "00", 1 -> "01", ...
        file_number = f"{i:02d}"

        t = threading.Thread(
            target=_start_inserts_on_node,
            args=(node_addr, file_number, results, i)
        )
        threads.append(t)

    # Start all threads nearly simultaneously
    for t in threads:
        t.start()

    # Wait for them to finish
    for t in threads:
        t.join()

    print("=== Distributed Insert Experiment Results ===")
    for res in results:
        if "error" in res:
            print(f"[{res['node']}] file_number={res['file_number']} => ERROR: {res['error']}")
        else:
            print(f"[{res['node']}] file_number={res['file_number']} => "
                  f"node_response={res['node_response']}, "
                  f"request_duration={res['request_duration']}s")
    print("==============================================")


if __name__ == "__main__":
    # Example usage: call the function for 5 nodes
    run_distributed_insert_experiment("127.0.0.1:8000", num_nodes=5)
