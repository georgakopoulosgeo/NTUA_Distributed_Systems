# client.py
import argparse
import requests

def main():
    # Παράμετρος για την διεύθυνση του κόμβου στον οποίο θα στέλνονται τα αιτήματα.
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", type=str, required=True, help="Διεύθυνση κόμβου σε μορφή ip:port")
    args = parser.parse_args()
    node_addr = args.node

    while True:
        print("\nChordify Client")
        print("1. Insert <key> <value>")
        print("2. Query <key>")
        print("3. Delete <key>")
        print("4. Overlay")
        print("5. Exit")
        choice = input("Επιλογή: ")

        if choice == "1":
            key = input("Key: ")
            value = input("Value: ")
            url = f"http://{node_addr}/insert"
            payload = {"key": key, "value": value}
            try:
                response = requests.post(url, json=payload)
                print("Response:", response.json())
            except Exception as e:
                print("Σφάλμα κατά την αποστολή:", e)
        elif choice == "2":
            key = input("Key: ")
            url = f"http://{node_addr}/query/{key}"
            try:
                response = requests.get(url)
                print("Response:", response.json())
            except Exception as e:
                print("Σφάλμα κατά την αποστολή:", e)
        elif choice == "3":
            key = input("Key: ")
            url = f"http://{node_addr}/delete"
            payload = {"key": key}
            try:
                response = requests.post(url, json=payload)
                print("Response:", response.json())
            except Exception as e:
                print("Σφάλμα κατά την αποστολή:", e)
        elif choice == "4":
            url = f"http://{node_addr}/overlay"
            try:
                response = requests.get(url)
                print("Overlay:", response.json())
            except Exception as e:
                print("Σφάλμα κατά την αποστολή:", e)
        elif choice == "5":
            break
        else:
            print("Μη έγκυρη επιλογή, δοκιμάστε ξανά.")

if __name__ == "__main__":
    main()
