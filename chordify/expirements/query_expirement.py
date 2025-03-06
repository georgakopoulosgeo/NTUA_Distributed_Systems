import requests
import threading
import time

def get_overlay(bootstrap_addr):
    """
    Fetches the overlay (ring info) from the given bootstrap node.
    Expected JSON format:
      { "ring": [ { "id": ..., "entryIp": ..., "port": ... }, ... ] }
    """
    url = f"http://{bootstrap_addr}/overlay"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def _start_queries_on_node(node_addr, file_number, results, index):
    """
    Thread worker that POSTs to /start_queries on node_addr with the given file_number.
    Stores the result (or error) in results[index].
    """
    url = f"http://{node_addr}/start_queries"
    payload = {"file_number": file_number}
    start_time = time.time()
    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()  # Expected to include "status", "queried", "time_seconds", etc.
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

def run_distributed_query_experiment(bootstrap_addr, num_nodes=5):
    """
    1. Fetches the overlay from the bootstrap node.
    2. Sorts the ring entries by 'id'.
    3. For the first num_nodes, spawns a thread that sends a /start_queries request.
       The file_number is set as a two-digit string (e.g. "00", "01", etc.).
    4. Waits for all threads to finish and prints the results.
    """
    overlay_data = get_overlay(bootstrap_addr)
    ring = overlay_data.get("ring", [])

    if len(ring) < num_nodes:
        print(f"Overlay only has {len(ring)} nodes, but we need {num_nodes}. Aborting.")
        return

    # Sort the ring entries by node 'id' (adjust key as needed)
    ring = sorted(ring, key=lambda x: x["id"])

    threads = []
    results = [None] * num_nodes

    # For each node, create a thread that calls /start_queries
    for i, entry in enumerate(ring[:num_nodes]):
        # If running on the host, you might use "127.0.0.1" with published ports.
        node_ip = "127.0.0.1"
        node_port = entry["port"]  # e.g., "8001"
        node_addr = f"{node_ip}:{node_port}"
        file_number = f"{i:02d}"  # e.g. "00", "01", etc.
        t = threading.Thread(
            target=_start_queries_on_node,
            args=(node_addr, file_number, results, i)
        )
        threads.append(t)

    # Start all threads almost simultaneously
    for t in threads:
        t.start()
    # Wait for all threads to finish
    for t in threads:
        t.join()

    print("=== Distributed Query Experiment Results ===")
    for res in results:
        if "error" in res:
            print(f"[{res['node']}] file_number={res['file_number']} => ERROR: {res['error']}")
        else:
            print(f"[{res['node']}] file_number={res['file_number']} => "
                  f"node_response={res['node_response']}, "
                  f"request_duration={res['request_duration']}s")
    print("==============================================")

if __name__ == "__main__":
    # Example usage: use the bootstrap node address and run the experiment on 5 nodes.
    run_distributed_query_experiment("127.0.0.1:8000", num_nodes=5)
