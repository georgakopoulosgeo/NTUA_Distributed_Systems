# bootstrap.py
import argparse
from node import Node
from api import app

if __name__ == '__main__':
    # Διαβάζουμε παραμέτρους γραμμής εντολών για τον bootstrap κόμβο.
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="IP διεύθυνση του bootstrap κόμβου")
    parser.add_argument("-p", "--port", type=int, default=8000, help="Θύρα του bootstrap κόμβου")
    args = parser.parse_args()

    # Δημιουργούμε το instance του κόμβου με την παράμετρο bootstrap=True.
    bootstrap_node = Node(ip=args.ip, port=args.port, is_bootstrap=True)
    
    # Αντιστοιχίζουμε το global node στο api module στον bootstrap κόμβο.
    import api
    api.node = bootstrap_node

    print("Εκκίνηση Bootstrap κόμβου στη διεύθυνση {}:{}".format(args.ip, args.port))
    app.run(host="0.0.0.0", port=args.port, debug=True)
