import argparse
import requests
from colorama import Fore, Style, init

# Initialize colorama so ANSI escape sequences will work on all platforms.
init(autoreset=True)

def insert_cmd(node_addr, key, value):
    url = f"http://{node_addr}/insert"
    payload = {"key": key, "value": value}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(Fore.GREEN + "\n[Insert successful]" + Style.RESET_ALL)
        print(response.json())
        print()  # blank line
    except Exception as e:
        print(Fore.RED + "\n[Error during insert]" + Style.RESET_ALL, e)
        print()

def query_cmd(node_addr, key):
    # Using local_query endpoint for synchronous response
    url = f"http://{node_addr}/local_query"
    params = {"key": key}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        print(Fore.GREEN + "\n[Query result]" + Style.RESET_ALL)
        print(response.json())
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
        print(response.json())
        print()  # blank line
    except Exception as e:
        print(Fore.RED + "\n[Error during delete]" + Style.RESET_ALL, e)
        print()

def join_cmd(node_addr, ip, port, node_id):
    """
    Sends a join request to the target node (which must be the bootstrap node).
    The payload includes the joining node's ip, port, and id.
    """
    url = f"http://{node_addr}/join"
    payload = {"ip": ip, "port": port, "id": node_id}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(Fore.GREEN + "\n[Join successful]" + Style.RESET_ALL)
        print(response.json())
        print()  # blank line
    except Exception as e:
        print(Fore.RED + "\n[Error during join]" + Style.RESET_ALL, e)
        print()

def depart_cmd(node_addr):
    """
    Sends a depart request to the target node.
    The node will handle its own graceful departure if it is not the bootstrap.
    """
    url = f"http://{node_addr}/depart"
    try:
        response = requests.post(url, json={})
        response.raise_for_status()
        print(Fore.GREEN + "\n[Depart successful]" + Style.RESET_ALL)
        print(response.json())
        print()  # blank line
    except Exception as e:
        print(Fore.RED + "\n[Error during depart]" + Style.RESET_ALL, e)
        print()

def overlay_cmd(node_addr):
    """
    Retrieves the current overlay (ring) information by sending a GET request to the /overlay endpoint.
    """
    url = f"http://{node_addr}/overlay"
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(Fore.GREEN + "\n[Overlay info]" + Style.RESET_ALL)
        print(response.json())
        print()  # blank line
    except Exception as e:
        print(Fore.RED + "\n[Error during overlay]" + Style.RESET_ALL, e)
        print()

def print_intro(node_addr):
    print(Fore.CYAN + f"Connected to node: http://{node_addr}" + Style.RESET_ALL)
    print(Fore.YELLOW + "Enter commands in the following format:" + Style.RESET_ALL)
    print("  Insert <key> <value>")
    print("  Query <key>")
    print("  Delete <key>")
    print("  Join <ip> <port> <id>")
    print("  Depart")
    print("  Overlay")
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

        elif cmd == "join":
            if len(tokens) != 4:
                print(Fore.RED + "Usage: Join <ip> <port> <id>" + Style.RESET_ALL)
                print()
                continue
            ip = tokens[1]
            port = tokens[2]
            node_id = tokens[3]
            join_cmd(node_addr, ip, port, node_id)

        elif cmd == "depart":
            if len(tokens) != 1:
                print(Fore.RED + "Usage: Depart" + Style.RESET_ALL)
                print()
                continue
            depart_cmd(node_addr)

        elif cmd == "overlay":
            if len(tokens) != 1:
                print(Fore.RED + "Usage: Overlay" + Style.RESET_ALL)
                print()
                continue
            overlay_cmd(node_addr)

        else:
            print(Fore.RED + "Invalid command. Use Insert, Query, Delete, Join, Depart, or Overlay." + Style.RESET_ALL)
            print()

if __name__ == "__main__":
    main()
