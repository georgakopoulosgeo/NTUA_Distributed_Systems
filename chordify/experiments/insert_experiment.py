import argparse
import requests
import threading
import time

def get_overlay(bootstrap_addr):
    url = f"http://{bootstrap_addr}/overlay"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def get_info(bootstrap_addr):
    url = f"http://{bootstrap_addr}/nodeinfo"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    return {
        "replication_factor": data.get("replication_factor"),
        "consistency_mode": data.get("consistency_mode")
    }

def _start_inserts_on_node(node_addr, file_number, results, index):
    # Thread worker that POSTs to /start_inserts on node_addr with the given file_number.
    url = f"http://{node_addr}/start_inserts"
    payload = {"file_number": file_number}
    start_time = time.time()

    try:
        r = requests.post(url, json=payload, timeout=248)
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

def run_distributed_insert_experiment(bootstrap_addr, num_nodes=5, local_flag=False):
    overlay_data = get_overlay(bootstrap_addr)
    ring = overlay_data.get("ring", [])

    system_info = get_info(bootstrap_addr)
    replication_factor = system_info.get("replication_factor")
    consistency_mode = system_info.get("consistency_mode")

    if len(ring) < num_nodes:
        print(f"Overlay only has {len(ring)} nodes, but we need {num_nodes}. Aborting.")
        return

    # Sort the ring entries by node ID (adjust if 'id' is not numeric)
    ring = sorted(ring, key=lambda x: x["id"])

    threads = []
    results = [None] * num_nodes

    # For each node, create a thread that calls /start_inserts
    for i, entry in enumerate(ring[:num_nodes]):
        if local_flag:
            node_ip = "127.0.0.1"  # When Running in Docker use the localhost
        else:
            node_ip = entry["ip"]
        node_port = entry["port"]
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
    print(f"Replication Factor: {replication_factor}, Consistency Mode: {consistency_mode}")
    for res in results:
        if "error" in res:
            print(f"[{res['node']}] file_number={res['file_number']} => ERROR: {res['error']}")
        else:
            print(f"[{res['node']}] file_number={res['file_number']} => "
                  f"node_response={res['node_response']}, "
                  f"request_duration={res['request_duration']}s, "
                  f"write throughput={res['node_response']['inserted'] / res['request_duration']:.2f} ops/sec")
    print("==============================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distributed Request Experiment")
    parser.add_argument("--bootstrap_ip", type=str, default="127.0.0.1", help="IP address of the bootstrap node")
    parser.add_argument("--bootstrap_port", type=int, default=8000, help="Port of the bootstrap node")
    parser.add_argument("--num_nodes", type=int, default=5, help="Number of nodes to run the experiment on")
    # Flag if running locally
    parser.add_argument("--local", action="store_true", help="Run locally")
    args = parser.parse_args()
    local_flag = args.local

    bootstrap_addr = f"{args.bootstrap_ip}:{args.bootstrap_port}"
    run_distributed_insert_experiment(bootstrap_addr, args.num_nodes, local_flag)

# python3 insert_experiment.py --bootstrap_ip 10.0.62.44 --bootstrap_port 8000 --num_nodes 10