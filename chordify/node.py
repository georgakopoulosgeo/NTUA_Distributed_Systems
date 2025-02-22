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
        self.successor = {}  # Πληροφορίες για τον επόμενο κόμβο στο δακτύλιο
        self.predecessor = {} # Πληροφορίες για τον προηγούμενο κόμβο (αν χρειαστεί)
        self.data_store = {}   # Αποθήκη για τα key-value δεδομένα


    def compute_hash(self, key):
        # Υπολογισμός του SHA1 hash ενός string και επιστροφή ως ακέραιος.
        h = hashlib.sha1(key.encode('utf-8')).hexdigest()
        return int(h, 16)

    def update_neighbors(self, successor, predecessor):
        # Ενημέρωση των δεδομένων για τον successor και τον predecessor.
        self.successor = successor
        self.predecessor = predecessor

    def is_responsible(self, key_hash: int) -> bool:
        # Έλεγχος αν ο κόμβος είναι υπεύθυνος για ένα key με βάση το hash του.
        if self.is_bootstrap:
            return True
        # Έλεγχος αν το key_hash είναι μέσα στο διάστημα (predecessor, self]
        if self.predecessor["id"] < self.id:
            return self.predecessor["id"] < key_hash <= self.id
        else:
            return self.predecessor["id"] < key_hash or key_hash <= self.id



    def insert(self, key: str, value: str) -> bool:
        # Υλοποιεί το insert του <key, value> ζεύγους σύμφωνα με τον Chord,
        key_hash = self.compute_hash(key)
        # print(f"[{self.ip}:{self.port}] Αίτημα insert για το key '{key}' (hash: {key_hash}).")
        if self.is_responsible(key_hash):
            # Εάν το key υπάρχει ήδη, ενημέρωσε το value (concat)
            if key in self.data_store:
                self.data_store[key] += f";{value}"
            else:
                self.data_store[key] = value
            print(f"[{self.ip}:{self.port}] Αποθήκευσε το key '{key}' (hash: {key_hash}) τοπικά.")
            return True
        else:
            # Προώθησε το αίτημα στον successor.
            #{
            #    "id": entry["id"],
            #    "ip": entry["ip"],
            #    "port": entry["port"]
            #}
            successor_ip = self.successor.get("ip")
            successor_port = self.successor.get("port")
            # Αν η ip του successor είναι 0.0.0.0 τοτε χρησιμοοποίησε την ip του bootstrap
            if successor_ip == "0.0.0.0":
                successor_ip = self.bootstrap_ip
            url = f"http://{successor_ip}:{successor_port}/insert"
            try:
                print(f"[{self.ip}:{self.port}] Προώθηση του key '{key}' (hash: {key_hash}) στον successor {successor_ip}:{successor_port}.")
                response = requests.post(url, json={"key": key, "value": value})
                # Αναμενόμενη επιστροφή από τον κόμβο-στόχο
                return response.json().get("result", False)
            except Exception as e:
                print(f"Σφάλμα κατά την προώθηση στο {successor_ip}:{successor_port}: {e}")
                return False

    def query(self, key: str) -> str:
        key_hash = self.compute_hash(key)
        print(f"[{self.ip}:{self.port}] Query for key '{key}' (hash: {key_hash})")

        if self.is_responsible(key_hash):
            print(f"[{self.ip}:{self.port}] Responsible for key '{key}', returning result.")
            return self.data_store.get(key, None)
        
        successor_ip = self.successor.get("ip")
        successor_port = self.successor.get("port")

        if not successor_ip or not successor_port:
            print(f"[{self.ip}:{self.port}] No valid successor! Cannot forward query.")
            return None

        url = f"http://{successor_ip}:{successor_port}/query?key={key}"
        print(f"[{self.ip}:{self.port}] Forwarding query to {successor_ip}:{successor_port}")

        try:
            response = requests.get(url)
            response_data = response.json()
            print(f"[{self.ip}:{self.port}] Received response: {response_data}")
            return response_data.get("result", None)
        except Exception as e:
            print(f"[{self.ip}:{self.port}] Error forwarding query: {e}")
            return None
        
    def query_all(self, origin: str = None, aggregated_data: dict = None) -> dict:
        """
        Επεκτάσιμη λειτουργία για το query "*" που συγκεντρώνει όλα τα <key, value> ζεύγη.
        Χρησιμοποιούμε το origin για να γνωρίζουμε πότε έχει ολοκληρωθεί ο κύκλος.
        """
        # Αν δεν έχει δοθεί origin, ο τρέχων κόμβος είναι ο εκκινητής
        if origin is None:
            origin = f"{self.ip}:{self.port}"
        # Αρχικοποίηση του aggregated_data
        if aggregated_data is None:
            aggregated_data = {}

        # Προσθέτουμε τα τοπικά δεδομένα
        aggregated_data.update(self.data_store)
        
        successor_ip = self.successor.get("ip")
        successor_port = self.successor.get("port")
        successor_identifier = f"{successor_ip}:{successor_port}"
        
        # Εάν ο επόμενος κόμβος είναι ο κόμβος εκκίνησης, τότε ο κύκλος έχει ολοκληρωθεί
        if successor_identifier == origin:
            return aggregated_data
        else:
            url = f"http://{successor_ip}:{successor_port}/query_all"
            payload = {
                "origin": origin,
                "aggregated_data": aggregated_data
            }
            try:
                print(f"[{self.ip}:{self.port}] Προώθηση του wildcard query '*' στον successor {successor_identifier}.")
                response = requests.post(url, json=payload)
                # Αναμένουμε ότι η απάντηση θα έχει το πλήρες aggregated_data
                return response.json().get("value", aggregated_data)
            except Exception as e:
                print(f"Σφάλμα κατά την προώθηση του wildcard query στο {successor_identifier}: {e}")
                return aggregated_data

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

