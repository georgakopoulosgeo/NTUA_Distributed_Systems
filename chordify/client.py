# client.py
import argparse
import requests

def insert_cmd(node_addr):
    key = input("Key: ")
    value = input("Value: ")
    url = f"http://{node_addr}/insert"
    payload = {"key": key, "value": value}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Επιτυχής εισαγωγή/ενημέρωση:", response.json())
    except Exception as e:
        print("Σφάλμα κατά την αποστολή:", e)

def query_cmd(node_addr):
    key = input("Key: ")
    url = f"http://{node_addr}/query/{key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        print("Αποτέλεσμα query:", response.json())
    except Exception as e:
        print("Σφάλμα κατά την αποστολή:", e)

def delete_cmd(node_addr):
    key = input("Key: ")
    url = f"http://{node_addr}/delete"
    payload = {"key": key}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Επιτυχής διαγραφή:", response.json())
    except Exception as e:
        print("Σφάλμα κατά την αποστολή:", e)

def overlay_cmd(node_addr):
    url = f"http://{node_addr}/overlay"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if "ring" in data:
            print("Overlay (Ring):")
            for node in data["ring"]:
                print(f"  Node {node['ip']}:{node['port']} (id={node['id']}), "
                      f"Predecessor: {node['predecessor']['id']}, "
                      f"Successor: {node['successor']['id']}")
        else:
            print("Απάντηση:", data)
    except Exception as e:
        print("Σφάλμα κατά την αποστολή:", e)

def depart_cmd(node_addr):
    url = f"http://{node_addr}/depart"
    try:
        response = requests.post(url)
        response.raise_for_status()
        print("Αποχώρηση επιτυχής:", response.json())
        return True
    except Exception as e:
        print("Σφάλμα κατά την αποχώρηση:", e)
        return False

def print_menu():
    print("\nChordify Client")
    print("1. Insert <key> <value>")
    print("2. Query <key>")
    print("3. Delete <key>")
    print("4. Overlay")
    print("5. Depart")
    print("6. Exit")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", type=str, required=True,
                        help="Διεύθυνση κόμβου σε μορφή ip:port (π.χ. node1:8001)")
    args = parser.parse_args()
    node_addr = args.node

    print(f"Συνδεδεμένος με τον κόμβο: http://{node_addr}")
    print_menu()
    while True:
        choice = input("Επιλογή: ").strip()
        if choice == "1":
            insert_cmd(node_addr)
        elif choice == "2":
            query_cmd(node_addr)
        elif choice == "3":
            delete_cmd(node_addr)
        elif choice == "4":
            overlay_cmd(node_addr)
        elif choice == "5":
            if depart_cmd(node_addr):
                break  # Κλείνουμε το client αφού ο κόμβος αποχωρήσει
        elif choice == "6":
            print("Έξοδος από το client.")
            break
        else:
            print("Μη έγκυρη επιλογή, δοκιμάστε ξανά.")

if __name__ == "__main__":
    main()
