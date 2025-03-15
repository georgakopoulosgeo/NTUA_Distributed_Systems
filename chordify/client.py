import argparse
import requests
import json
import sys
from colorama import Fore, Style, init

# Initialize colorama so ANSI escape sequences work on all platforms.
init(autoreset=True)

def display_insert_response(resp):
    """
    Formats and displays the insert response in a user-friendly way.
    """
    print(Fore.GREEN + "\n[Insert successful]" + Style.RESET_ALL)
    message = resp.get("message", "No message provided")
    print(Fore.CYAN + "Message:" + Style.RESET_ALL, message)
    
    ip = resp.get("ip", "N/A")
    print(Fore.CYAN + "IP:" + Style.RESET_ALL, ip)
    
    data_store = resp.get("data_store", {})
    if data_store:
        print(Fore.CYAN + "Data Store:" + Style.RESET_ALL)
        for key, value in data_store.items():
            print(f"  {key}: {value}")
    else:
        print(Fore.CYAN + "Data Store:" + Style.RESET_ALL, "{}")
    
    result = resp.get("result", None)
    if result is not None:
        print(Fore.CYAN + "Result:" + Style.RESET_ALL, result)
    print()

def insert_cmd(node_addr, key, value):
    url = f"http://{node_addr}/insert"
    payload = {"key": key, "value": value}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        resp_json = response.json()
        display_insert_response(resp_json)
    except Exception as e:
        print(Fore.RED + "\n[Error during insert]" + Style.RESET_ALL, e)
        print()

def display_query_response(resp):
    """
    Formats and displays the query response in a user-friendly way.
    This function handles both single key queries and the "*" query.
    """
    print(Fore.GREEN + "\n[Query result]" + Style.RESET_ALL)
    # Check if the response is for the '*' query (all songs)
    if "all_songs" in resp:
        all_songs = resp.get("all_songs", {})
        nodes_count = resp.get("nodes_count", "N/A")
        original_songs_count = resp.get("original_songs_count", "N/A")
        replica_songs_count = resp.get("replica_songs_count", "N/A")
        print(Fore.CYAN + "Nodes Count:" + Style.RESET_ALL, nodes_count)
        print(Fore.CYAN + "Original Songs Count:" + Style.RESET_ALL, original_songs_count)
        print(Fore.CYAN + "Replica Songs Count:" + Style.RESET_ALL, replica_songs_count)
        print()
        for node, songs in all_songs.items():
            print(Fore.CYAN + f"Node {node}:" + Style.RESET_ALL)
            original = songs.get("original_songs", {})
            replica = songs.get("replica_songs", {})
            if original:
                print("  " + Fore.YELLOW + "Original Songs:" + Style.RESET_ALL)
                for k, v in original.items():
                    print(f"    {k}: {v}")
            else:
                print("  " + Fore.YELLOW + "Original Songs:" + Style.RESET_ALL, "{}")
            if replica:
                print("  " + Fore.YELLOW + "Replica Songs:" + Style.RESET_ALL)
                for k, v in replica.items():
                    print(f"    {k}: {v}")
            else:
                print("  " + Fore.YELLOW + "Replica Songs:" + Style.RESET_ALL, "{}")
            print("-" * 40)
        print()
    else:
        # Single key query response
        result_from = resp.get("Result from", "N/A")
        status = resp.get("Status", "N/A")
        key = resp.get("Key", "N/A")
        result_value = resp.get("result", "N/A")
        if result_from == "N/A":
            print(Fore.RED + "Key not found." + Style.RESET_ALL)
            print()
        else:
            print(Fore.CYAN + "Result from:" + Style.RESET_ALL, result_from)
            print(Fore.CYAN + "Status:" + Style.RESET_ALL, status)
            print(Fore.CYAN + "Key:" + Style.RESET_ALL, key)
            print(Fore.CYAN + "Value:" + Style.RESET_ALL, result_value)
            print()

def query_cmd(node_addr, key):
    url = f"http://{node_addr}/query"
    params = {"key": key}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        resp_json = response.json()
        display_query_response(resp_json)
    except Exception as e:
        print(Fore.RED + "\n[Error during query]" + Style.RESET_ALL, e)
        print()

def display_delete_response(resp):
    """
    Formats and displays the delete response in a user-friendly way.
    """
    print(Fore.GREEN + "\n[Delete successful]" + Style.RESET_ALL)
    message = resp.get("message", "No message provided")
    print(Fore.CYAN + "Message:" + Style.RESET_ALL, message)
    
    ip = resp.get("ip", "N/A")
    print(Fore.CYAN + "IP:" + Style.RESET_ALL, ip)
    
    data_store = resp.get("data_store", {})
    if data_store:
        print(Fore.CYAN + "Data Store:" + Style.RESET_ALL)
        for key, value in data_store.items():
            print(f"  {key}: {value}")
    else:
        print(Fore.CYAN + "Data Store:" + Style.RESET_ALL, "{}")
    
    result = resp.get("result", None)
    if result is not None:
        print(Fore.CYAN + "Result:" + Style.RESET_ALL, result)
    print()

def delete_cmd(node_addr, key):
    url = f"http://{node_addr}/delete"
    payload = {"key": key}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        resp_json = response.json()
        display_delete_response(resp_json)
    except Exception as e:
        print(Fore.RED + "\n[Error during delete]" + Style.RESET_ALL, e)
        print()

def display_overlay_info(info):
    """
    Formats and displays the overlay (ring) information in a user-friendly way.
    """
    print(Fore.GREEN + "\n[Overlay info]" + Style.RESET_ALL)
    ring = info.get("ring", [])
    if not ring:
        print(Fore.CYAN + "No nodes in the ring." + Style.RESET_ALL)
        return

    for idx, node in enumerate(ring, start=1):
        print(Fore.CYAN + f"Node {idx}:" + Style.RESET_ALL)
        print("  " + Fore.YELLOW + "ID:" + Style.RESET_ALL, node.get("id"))
        print("  " + Fore.YELLOW + "IP:" + Style.RESET_ALL, node.get("ip"))
        print("  " + Fore.YELLOW + "Port:" + Style.RESET_ALL, node.get("port"))
        print("  " + Fore.YELLOW + "Predecessor:" + Style.RESET_ALL, node.get("predecessor"))
        print("  " + Fore.YELLOW + "Successor:" + Style.RESET_ALL, node.get("successor"))
        print("-" * 40)
    print()

def overlay_cmd(node_addr):
    """
    Retrieves and displays the overlay (ring) information in a formatted manner.
    """
    url = f"http://{node_addr}/overlay"
    try:
        response = requests.get(url)
        response.raise_for_status()
        overlay_data = response.json()
        display_overlay_info(overlay_data)
    except Exception as e:
        print(Fore.RED + "\n[Error during overlay]" + Style.RESET_ALL, e)
        print()

def depart_cmd(node_addr):
    """
    Sends a depart request to the target node and exits the client if the node departs gracefully.
    """
    url = f"http://{node_addr}/depart"
    try:
        response = requests.post(url, json={})
        response.raise_for_status()
        print(Fore.GREEN + "\n[Depart successful]" + Style.RESET_ALL)
        departure_response = response.json()
        print(departure_response)
        print()  # blank line

        if isinstance(departure_response, dict):
            message = departure_response.get("message", "").lower()
        elif isinstance(departure_response, str):
            message = departure_response.lower()
        else:
            message = ""

        if "node departed gracefully" in message:
            print(Fore.MAGENTA + "Exiting client." + Style.RESET_ALL)
            sys.exit(0)
        else:
            sys.exit(0)
    except Exception as e:
        print(Fore.RED + "\n[Error during depart]" + Style.RESET_ALL, e)
        print()

def display_node_info(info):
    """
    Formats and displays the node information in a user-friendly way.
    """
    print(Fore.GREEN + "\n[Node info]" + Style.RESET_ALL)
    print(Fore.CYAN + "Node ID:" + Style.RESET_ALL, info.get("id"))
    print(Fore.CYAN + "IP:" + Style.RESET_ALL, info.get("ip"))
    print(Fore.CYAN + "Port:" + Style.RESET_ALL, info.get("port"))
    print(Fore.CYAN + "Consistency Mode:" + Style.RESET_ALL, info.get("consistency_mode"))
    print(Fore.CYAN + "Replication Factor:" + Style.RESET_ALL, info.get("replication_factor"))

    data_store = info.get("data_store", {})
    print(Fore.CYAN + "Data Store:" + Style.RESET_ALL)
    if data_store:
        for key, val in data_store.items():
            print(f"  {key}: {val}")
    else:
        print("  {}")

    replica_store = info.get("replica_store", {})
    print(Fore.CYAN + "Replica Store:" + Style.RESET_ALL)
    if replica_store:
        for key, val in replica_store.items():
            print(f"  {key}: {val}")
    else:
        print("  {}")

    predecessor = info.get("predecessor")
    if predecessor:
        print(Fore.CYAN + "Predecessor:" + Style.RESET_ALL)
        print("  ID: ", predecessor.get("id"))
        print("  IP: ", predecessor.get("ip"))
        print("  Port: ", predecessor.get("port"))

    successor = info.get("successor")
    if successor:
        print(Fore.CYAN + "Successor:" + Style.RESET_ALL)
        print("  ID: ", successor.get("id"))
        print("  IP: ", successor.get("ip"))
        print("  Port: ", successor.get("port"))

    print()

def nodeinfo_cmd(node_addr):
    """
    Retrieves the node information from the /nodeinfo endpoint and displays it nicely.
    """
    url = f"http://{node_addr}/nodeinfo"
    try:
        response = requests.get(url)
        response.raise_for_status()
        info = response.json()
        display_node_info(info)
    except Exception as e:
        print(Fore.RED + "\n[Error during nodeinfo]" + Style.RESET_ALL, e)
        print()

def help_cmd():
    """
    Prints help information for all available commands.
    """
    help_text = """
Available commands:
    Insert <key> <value>  - Insert a key-value pair into the network.
    Query <key>           - Retrieve the value associated with a given key.
    Delete <key>          - Delete the key-value pair from the network.
    Overlay               - Display the current network overlay (topology).
    Nodeinfo              - Display the node information.
    Depart                - Gracefully remove the node from the network and exit the client.
    Help                  - Show this help message.
    Exit                  - Quit the client.
"""
    print(Fore.CYAN + help_text + Style.RESET_ALL)

def print_intro(node_addr):
    print(Fore.CYAN + f"Connected to node: http://{node_addr}" + Style.RESET_ALL)
    print(Fore.YELLOW + "Enter commands in the following format:" + Style.RESET_ALL)
    print("  Insert <key> <value>")
    print("  Query <key>")
    print("  Delete <key>")
    print("  Overlay")
    print("  Nodeinfo")
    print("  Depart")
    print("  Help")
    print(Fore.YELLOW + "Type 'Exit' to quit." + Style.RESET_ALL)
    print()

def main():
    parser = argparse.ArgumentParser(
        description="Client for interacting with a specific node in the distributed system"
    )
    parser.add_argument(
        "--node", 
        type=str, 
        required=True,
        help="Target node address in the format ip:port (e.g., 127.0.0.1:8001)"
    )
    args = parser.parse_args()
    node_addr = args.node

    # --- Health Check: ensure the node is reachable and responding ---
    try:
        url = f"http://{node_addr}/overlay"
        response = requests.get(url, timeout=2)
        response.raise_for_status()
    except Exception as e:
        print(Fore.RED + f"\n[Error] Unable to connect to node at {node_addr}. Node is not part of the system." + Style.RESET_ALL)
        sys.exit(1)
    # ----------------------------------------------------------------

    print_intro(node_addr)

    while True:
        try:
            command_line = input(Fore.BLUE + "> " + Style.RESET_ALL).strip()
        except KeyboardInterrupt:
            print(Fore.MAGENTA + "\nExiting client." + Style.RESET_ALL)
            break

        if not command_line:
            continue
        if command_line.lower() == "exit":
            print(Fore.MAGENTA + "Exiting client." + Style.RESET_ALL)
            break

        tokens = command_line.split()
        cmd = tokens[0].lower()

        if cmd == "insert":
            if len(tokens) < 3:
                print(Fore.RED + "Usage: Insert <key> <value>" + Style.RESET_ALL)
                print()
                continue
            key = tokens[1]
            value = " ".join(tokens[2:])
            insert_cmd(node_addr, key, value)

        elif cmd == "query":
            if len(tokens) != 2:
                print(Fore.RED + "Usage: Query <key>" + Style.RESET_ALL)
                print()
                continue
            key = tokens[1]
            query_cmd(node_addr, key)

        elif cmd == "delete":
            if len(tokens) != 2:
                print(Fore.RED + "Usage: Delete <key>" + Style.RESET_ALL)
                print()
                continue
            key = tokens[1]
            delete_cmd(node_addr, key)

        elif cmd == "overlay":
            if len(tokens) != 1:
                print(Fore.RED + "Usage: Overlay" + Style.RESET_ALL)
                print()
                continue
            overlay_cmd(node_addr)
        
        elif cmd == "nodeinfo":
            if len(tokens) != 1:
                print(Fore.RED + "Usage: Nodeinfo" + Style.RESET_ALL)
                print()
                continue
            nodeinfo_cmd(node_addr)

        elif cmd == "depart":
            if len(tokens) != 1:
                print(Fore.RED + "Usage: Depart" + Style.RESET_ALL)
                print()
                continue
            depart_cmd(node_addr)
            # depart_cmd will exit the client if successful.

        elif cmd == "help":
            help_cmd()

        else:
            print(Fore.RED + "Invalid command. Use Insert, Query, Delete, Overlay, Depart, Help, or Exit." + Style.RESET_ALL)
            print()

if __name__ == "__main__":
    main()
