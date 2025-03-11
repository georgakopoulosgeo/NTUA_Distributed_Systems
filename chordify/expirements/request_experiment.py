import argparse
import csv
import threading
import requests
import time
import os

def get_overlay(bootstrap_addr):
    url = f"http://{bootstrap_addr}/overlay"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()

def get_info(bootstrap_addr):
    url = f"http://{bootstrap_addr}/nodeinfo"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()

def to_set(value_str):
    if not value_str:
        return set()
    return set(x.strip() for x in value_str.split("|"))

def run_requests_on_node_with_logging(node_addr, file_number, results, logs_list, index):
    """
    Reads the file "requests_{file_number}.txt" and executes each request on the given node.
    Logs each operation (insert or query) with a timestamp.
    """
    file_path = os.path.join(".", "requests", f"requests_{file_number}.txt")
    
    total_queries = 0
    total_inserts = 0
    failed_queries = 0
    logs = []  # Each log entry is a dict that records details about the operation.

    try:
        with open(file_path, "r") as f:
            reader = csv.reader(f)
            command_index = 0
            for row in reader:
                if not row:
                    continue
                op = row[0].strip().lower()
                if op == "insert":
                    # Expecting: insert, key, value
                    if len(row) < 3:
                        print(f"[{node_addr}] Invalid insert command: {row}")
                        continue
                    key = row[1].strip()
                    value = row[2].strip()
                    payload = {"key": key, "value": value}
                    start_time = time.time()
                    try:
                        r = requests.post(f"http://{node_addr}/insert", json=payload, timeout=5)
                        end_time = time.time()
                        total_inserts += 1
                        logs.append({
                            "node": node_addr,
                            "file_number": file_number,
                            "command_index": command_index,
                            "operation": "insert",
                            "key": key,
                            "insert_value": value,
                            "returned_value": None,
                            "start_time": start_time,
                            "end_time": end_time,
                            "response_time": end_time - start_time,
                            "status": "sent"
                        })
                    except Exception as e:
                        print(f"[{node_addr}] Error in insert for key '{key}': {e}")
                        logs.append({
                            "node": node_addr,
                            "file_number": file_number,
                            "command_index": command_index,
                            "operation": "insert",
                            "key": key,
                            "insert_value": value,
                            "returned_value": None,
                            "start_time": start_time,
                            "end_time": None,
                            "response_time": None,
                            "status": f"error: {e}"
                        })
                elif op == "query":
                    # Expecting: query, key
                    if len(row) < 2:
                        print(f"[{node_addr}] Invalid query command: {row}")
                        continue
                    key = row[1].strip()
                    start_time = time.time()
                    try:
                        r = requests.get(f"http://{node_addr}/query?key={key}", timeout=5)
                        end_time = time.time()
                        total_queries += 1
                        if r.status_code == 200:
                            data = r.json()
                            logs.append({
                                "node": node_addr,
                                "file_number": file_number,
                                "command_index": command_index,
                                "operation": "query",
                                "key": key,
                                "insert_value": None,
                                "returned_value": data.get("result"),
                                "start_time": start_time,
                                "end_time": end_time,
                                "response_time": end_time - start_time,
                                "status": "queried"
                            })
                        else:
                            failed_queries += 1
                            logs.append({
                                "node": node_addr,
                                "file_number": file_number,
                                "command_index": command_index,
                                "operation": "query",
                                "key": key,
                                "insert_value": None,
                                "returned_value": None,
                                "start_time": start_time,
                                "end_time": end_time,
                                "response_time": end_time - start_time,
                                "status": "error: non-200"
                            })
                    except Exception as e:
                        failed_queries += 1
                        print(f"[{node_addr}] Error in query for key '{key}': {e}")
                        logs.append({
                            "node": node_addr,
                            "file_number": file_number,
                            "command_index": command_index,
                            "operation": "query",
                            "key": key,
                            "insert_value": None,
                            "returned_value": None,
                            "start_time": start_time,
                            "end_time": None,
                            "response_time": None,
                            "status": f"error: {e}"
                        })
                else:
                    print(f"[{node_addr}] Unknown command in row: {row}")
                command_index += 1
    except FileNotFoundError:
        results[index] = {"node": node_addr, "error": f"File not found: {file_path}"}
        logs_list[index] = []
        return

    results[index] = {
        "node": node_addr,
        "file_number": file_number,
        "total_queries": total_queries,
        "total_inserts": total_inserts,
        "failed_queries": failed_queries
    }
    logs_list[index] = logs

def compute_expected_values(global_logs, consistency_mode):
    """
    Build the expected value for each key using the order of committed inserts.
    Here we assume that each insert log has a 'commit_time' field set when the final callback is received.
    """
    expected_state = {}
    comparison_logs = []
    # For each operation in global_logs:
    if consistency_mode == "eventual":
        for log in global_logs:
            if log["operation"] == "insert":
                key = log["key"]
                val = log["insert_value"]
                commit_time = log.get("commit_time", log["end_time"])  # fallback if commit_time not available

                # Instead of updating expected_state immediately,
                # you may need to collect all inserts per key and sort them by commit_time.
                if key not in expected_state:
                    expected_state[key] = []
                expected_state[key].append((commit_time, val))
                # Append the insert log as-is (freshness does not apply to inserts)
                log_copy = log.copy()
                log_copy["expected_value"] = None
                log_copy["freshness"] = None
                comparison_logs.append(log_copy)
            elif log["operation"] == "query":
                key = log["key"]
                # Get all inserts for that key and sort them by commit_time
                insert_entries = sorted(expected_state.get(key, []), key=lambda x: x[0])
                # Build expected value by concatenating in commit order
                exp_val = " | ".join(val for _, val in insert_entries) if insert_entries else None
                log_copy = log.copy()
                log_copy["expected_value"] = exp_val
                returned_val = log.get("returned_value")
                if returned_val == False:
                    log_copy["freshness"] = ""
                else:
                    exp_val_set = to_set(exp_val)
                    returned_val_set = to_set(returned_val)
                    if exp_val_set == returned_val_set:
                        log_copy["freshness"] = "fresh"
                    else:
                        log_copy["freshness"] = "stale"
                comparison_logs.append(log_copy)
    else:
        expected_state = {}  # key -> list of tuples (order_val, value)
        for log in global_logs:
            if log["operation"] == "insert":
                key = log["key"]
                val = log["insert_value"]
                # Use commit_seq if available; otherwise fallback to commit_time or end_time.
                order_val = log.get("commit_seq", log.get("commit_time", log["end_time"]))
                if key not in expected_state:
                    expected_state[key] = []
                expected_state[key].append((order_val, val))
                log_copy = log.copy()
                log_copy["expected_value"] = None
                log_copy["freshness"] = None
                comparison_logs.append(log_copy)
            elif log["operation"] == "query":
                key = log["key"]
                insert_entries = sorted(expected_state.get(key, []), key=lambda x: x[0])
                exp_val = " | ".join(val for _, val in insert_entries) if insert_entries else None
                log_copy = log.copy()
                log_copy["expected_value"] = exp_val
                returned_val = log.get("returned_value")
                if returned_val == False:
                    log_copy["freshness"] = ""
                else:
                    exp_val_set = to_set(exp_val)
                    returned_val_set = to_set(returned_val)
                    if exp_val_set == returned_val_set:
                        log_copy["freshness"] = "fresh"
                    else:
                        log_copy["freshness"] = "stale"
                comparison_logs.append(log_copy)
    return comparison_logs


def run_distributed_request_experiment_with_comparison(bootstrap_addr, num_nodes=5, local_flag=False):
    """
    Runs the distributed experiment:
      1. Retrieves overlay and system info.
      2. Spawns a thread per node to process its request file.
      3. Aggregates results and logs.
      4. Combines logs from all nodes, computes expected values, and compares query results.
      5. Prints the total fresh and stale read counts.
      6. Writes a CSV file with detailed comparison.
    """
    overlay_data = get_overlay(bootstrap_addr)
    ring = overlay_data.get("ring", [])
    if len(ring) < num_nodes:
        print(f"Overlay only has {len(ring)} nodes, but we need {num_nodes}. Aborting experiment.")
        return

    system_info = get_info(bootstrap_addr)
    replication_factor = system_info.get("replication_factor")
    consistency_mode = system_info.get("consistency_mode")

    # Sort ring entries by a consistent key (e.g., 'id')
    ring = sorted(ring, key=lambda x: x["id"])
    threads = []
    results = [None] * num_nodes
    logs_per_node = [None] * num_nodes

    for i, entry in enumerate(ring[:num_nodes]):
        if local_flag:
            node_ip = "127.0.0.1"  # When Running in Docker use the localhost
        else:
            node_ip = entry["ip"]
        node_port = entry["port"]
        node_addr = f"{node_ip}:{node_port}"
        file_number = f"{i:02d}"
        t = threading.Thread(target=run_requests_on_node_with_logging, args=(node_addr, file_number, results, logs_per_node, i))
        threads.append(t)

    start_experiment = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    end_experiment = time.time()
    experiment_duration = end_experiment - start_experiment

    print("=== Distributed Request Experiment Results ===")
    print(f"Consistency Mode: {consistency_mode}, Replication Factor: {replication_factor}")
    for res in results:
        if "error" in res:
            print(f"[{res['node']}] ERROR: {res['error']}")
        else:
            print(f"[{res['node']}] File {res['file_number']}: Total Queries: {res['total_queries']}, Total Inserts: {res['total_inserts']}")
    print("Experiment Duration: {:.2f} seconds".format(experiment_duration))
    print("==============================================")

    # Combine all logs from all nodes and sort by start_time.
    global_logs = []
    for node_logs in logs_per_node:
        if node_logs:
            global_logs.extend(node_logs)
    global_logs.sort(key=lambda x: x["start_time"])

    # Compute expected values for queries and compare.
    comparison_logs = compute_expected_values(global_logs, consistency_mode)

    # Count fresh and stale reads.
    fresh_count = sum(1 for log in comparison_logs if log.get("freshness") == "fresh")
    stale_count = sum(1 for log in comparison_logs if log.get("freshness") == "stale")
    print("Fresh Reads: ", fresh_count)
    print("Stale Reads: ", stale_count)

    # Write detailed comparison logs to a CSV file.
    csv_filename = "comparison_log.csv"
    with open(csv_filename, "w", newline="") as csvfile:
        fieldnames = [
            "node", "file_number", "command_index", "operation", "key",
            "insert_value", "returned_value", "expected_value", "freshness",
            "start_time", "end_time", "response_time", "status"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for log in comparison_logs:
            writer.writerow(log)
    print(f"Detailed query comparison logs written to {csv_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distributed Request Experiment")
    parser.add_argument("--bootstrap_ip", type=str, default="127.0.0.1", help="IP address of the bootstrap node")
    parser.add_argument("--bootstrap_port", type=int, default=8000, help="Port of the bootstrap node")
    parser.add_argument("--num_nodes", type=int, default=5, help="Number of nodes to run the experiment on")
    parser.add_argument("--local", action="store_true", help="Run the experiment locally (on the host)")
    args = parser.parse_args()

    local_flag = args.local
    bootstrap_addr = f"{args.bootstrap_ip}:{args.bootstrap_port}"
    run_distributed_request_experiment_with_comparison(bootstrap_addr, args.num_nodes, local_flag)

# python3 request_experiment.py --bootstrap_ip 10.0.62.44 --bootstrap_port 8000 --num_nodes 10
