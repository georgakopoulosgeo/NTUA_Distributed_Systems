import argparse
import requests
import json
import sys
from colorama import Fore, Style, init

# Initialize colorama so ANSI escape sequences work on all platforms.
init(autoreset=True)

def insert_cmd(node_addr, key, value):
    url = f"http://{node_addr}/insert"
    payload = {"key": key, "value": value}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(Fore.GREEN + "\n[Insert successful]" + Style.RESET_ALL)
        # Pretty-print the JSON response with an indent of 4 spaces.
        formatted_output = json.dumps(response.json(), indent=4)
        print(formatted_output)
        print()  # blank line
    except Exception as e:
        print(Fore.RED + "\n[Error during insert]" + Style.RESET_ALL, e)
        print()

def query_cmd(node_addr, key):
    url = f"http://{node_addr}/query"
    params = {"key": key}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        print(Fore.GREEN + "\n[Query result]" + Style.RESET_ALL)
        # Pretty-print the JSON response with an indent of 4 spaces.
        formatted_output = json.dumps(response.json(), indent=4)
        print(formatted_output)
        print()  # blank line
    except Exception as e:
        print(Fore.RED + "\n[Error during query]" + Style.RESET_ALL, e)
        print()

def delete_cmd(node_addr, key):
    url = f"http://{node_addr}/delete"
    payload = {"key": key}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(Fore.GREEN + "\n[Delete successful]" + Style.RESET_ALL)
        # Pretty-print the JSON response with an indent of 4 spaces.
        formatted_output = json.dumps(response.json(), indent=4)
        print(formatted_output)
        print()  # blank line
    except Exception as e:
        print(Fore.RED + "\n[Error during delete]" + Style.RESET_ALL, e)
        print()

def overlay_cmd(node_addr):
    """
    Retrieves and pretty-prints the overlay (ring) information.
    """
    url = f"http://{node_addr}/overlay"
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(Fore.GREEN + "\n[Overlay info]" + Style.RESET_ALL)
        overlay_data = response.json()
        formatted_data = json.dumps(overlay_data, indent=4)
        print(formatted_data)
        print()  # blank line
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
