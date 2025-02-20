import hashlib
import requests

class Node:
    def __init__(self, ip, port, is_bootstrap=False):
        #Αρχικοποίηση κόμβου.
        #:param ip: Η IP διεύθυνση του κόμβου.
        #:param port: Η θύρα στην οποία ακούει ο κόμβος.
        #:param is_bootstrap: Αν ο κόμβος είναι bootstrap.
        self.ip = ip
        self.port = port
        self.is_bootstrap = is_bootstrap
        # Αν ο κόμβος δεν είναι bootstrap, υπολογίζουμε το id από το hash της ip:port.
        self.id = 0 if is_bootstrap else self.compute_hash(f"{self.ip}:{self.port}")
        self.successor = None  # Πληροφορίες για τον επόμενο κόμβο στο δακτύλιο
        self.predecessor = None  # Πληροφορίες για τον προηγούμενο κόμβο (αν χρειαστεί)
        self.data_store = {}   # Αποθήκη για τα key-value δεδομένα

    def compute_hash(self, key):
        # Υπολογισμός του SHA1 hash ενός string και επιστροφή ως ακέραιος.
        h = hashlib.sha1(key.encode('utf-8')).hexdigest()
        return int(h, 16)

    def update_neighbors(self, successor, predecessor):
        # Ενημέρωση των δεικτών για successor και predecessor.
        self.successor = successor
        self.predecessor = predecessor

    def insert(self, key, value):
        # Εισαγωγή (ή ενημέρωση) ενός key-value ζεύγους.
        # Στην περίπτωση του replication k=1 αποθηκεύουμε απλά το ζεύγος στο τοπικό data_store.
        self.data_store[key] = value
        return True

    def query(self, key):
        # Αναζήτηση ενός key στο τοπικό data_store.
        # Επιστρέφει το value αν βρεθεί, αλλιώς None.
        return self.data_store.get(key, None)

    def delete(self, key):
        # Διαγραφή ενός key από το data_store.
        # Επιστρέφει True αν διαγράφηκε, αλλιώς False.
        if key in self.data_store:
            del self.data_store[key]
            return True
        return False

    def join(self, bootstrap_ip, bootstrap_port):
        # Ο κόμβος που δεν είναι bootstrap καλεί αυτή τη μέθοδο για να εισέλθει στο δίκτυο.
        # Στέλνει αίτημα στον bootstrap κόμβο.
        url = f"http://{bootstrap_ip}:{bootstrap_port}/join"
        payload = {'ip': self.ip, 'port': self.port, 'id': self.id}
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                # Ενημέρωση του successor και του predecessor βάσει της απάντησης
                self.successor = data.get('successor', None)
                self.predecessor = data.get('predecessor', None)
                return True
            else:
                return False
        except Exception as e:
            print("Error joining network:", e)
            return False

    def depart(self):
        """
        Στην απλή «global ring» λογική, απλώς καλούμε τον bootstrap
        να μας αφαιρέσει από το ring. (Αν ήμασταν σε full Chord,
        θα ενημερώναμε successor, predecessor, κλπ.)
        """
        # Αν δεν είμαστε bootstrap, καλούμε τον bootstrap
        if not self.is_bootstrap:
            url = f"http://{self.bootstrap_ip}:{self.bootstrap_port}/remove_node"
            payload = {
                "id": self.id,
                "ip": self.ip,
                "port": self.port
            }
            try:
                r = requests.post(url, json=payload)
                if r.status_code == 200:
                    print(f"[{self.ip}:{self.port}] Departed gracefully from ring.")
                    return True
                else:
                    print(f"[{self.ip}:{self.port}] Depart error: {r.text}")
                    return False
            except Exception as e:
                print("Error calling remove_node on bootstrap:", e)
                return False
        else:
            # Αν είμαστε bootstrap, θεωρητικά δεν αποχωρούμε
            print("Bootstrap node does not depart.")
            return False

