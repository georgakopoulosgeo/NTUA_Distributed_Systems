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
        # Check if the node is responsible for a given key hash
        if self.is_bootstrap:
            return True
        # Check if the key hash is between the predecessor and the node id
        if self.predecessor["id"] < self.id:
            return self.predecessor["id"] < key_hash <= self.id
        else:
            return self.predecessor["id"] < key_hash or key_hash <= self.id



    def insert(self, key: str, value: str) -> bool:
        # Implement the insert operation for a key-value pair
        key_hash = self.compute_hash(key)
        # print(f"[{self.ip}:{self.port}] Αίτημα insert για το key '{key}' (hash: {key_hash}).")
        if self.is_responsible(key_hash):
            if key in self.data_store:
                self.data_store[key] += f" | {value}"
                print(f"[{self.ip}:{self.port}] Ενημερώθηκε το key '{key}' στον κόμβο {self.ip} (hash: {key_hash}).")
                return {
                    "result": True,
                    "message": f"Key '{key}' inserted to node {self.ip} (hash: {key_hash}).",
                    "data_store": self.data_store,
                    "ip": self.ip
                }
            else:
                # If the key does not exist, create a new entry
                self.data_store[key] = value
                print(f"[{self.ip}:{self.port}] Εισαγωγή του key '{key}' στον κόμβο {self.ip} (hash: {key_hash}).")
                return {
                    "result": True,
                    "message": f"Key '{key}' updated on node {self.ip} (hash: {key_hash}).",
                    "data_store": self.data_store,
                    "ip": self.ip
                }
        else:
            # Forward the request to the successor
            #{
            #    "id": entry["id"],
            #    "ip": entry["ip"],
            #    "port": entry["port"]
            #}
            successor_ip = self.successor.get("ip")
            successor_port = self.successor.get("port")
            # If the successor is the bootstrap, we need to use the bootstrap IP
            if successor_ip == "0.0.0.0":
                successor_ip = self.bootstrap_ip
            url = f"http://{successor_ip}:{successor_port}/insert"
            try:
                print(f"[{self.ip}:{self.port}] Προώθηση του key '{key}' (hash: {key_hash}) στον successor {successor_ip}:{successor_port}.")
                response = requests.post(url, json={"key": key, "value": value})
                # Return the response from the successor
                return response.json()
            except Exception as e:
                return {
                "result": False,
                "error": f"Forwarding insert request failed: {e}"
              }

    def query(self, key: str) -> str:
        key_hash = self.compute_hash(key)
        if self.is_responsible(key_hash):
            return self.data_store.get(key, None)
        else:
            successor_ip = self.successor.get("ip")
            successor_port = self.successor.get("port")
            if successor_ip == "0.0.0.0":
                successor_ip = self.bootstrap_ip
            url = f"http://{successor_ip}:{successor_port}/query?key={key}"
            try:
                response = requests.get(url)
                return response.json().get("result", None)
            except Exception as e:
                print(f"Error forwarding query request to {successor_ip}:{successor_port}: {e}")
                return None
        
    def query_wildcard(self, visited=None):
        """
        Handles wildcard '*' queries by aggregating all songs from the DHT ring.
        """
        if visited is None:
            visited = set()

        origin = f"{self.ip}:{self.port}"

        # If we've already visited this node, we've completed the loop
        if origin in visited:
            return self.data_store

        visited.add(origin)  # Mark this node as visited
        all_songs = self.data_store.copy()  # Start with local data

        successor_ip = self.successor.get("ip")
        successor_port = self.successor.get("port")
        successor_identifier = f"{successor_ip}:{successor_port}"

        # Prevent infinite looping by checking if we reached the original node
        if successor_identifier in visited:
            return all_songs

        # Forward query to the next node in the ring
        url = f"http://{successor_ip}:{successor_port}/query?key=*"
        try:
            print(f"[{self.ip}:{self.port}] Forwarding wildcard query '*' to {successor_identifier}.")
            response = requests.get(url)
            if response.status_code == 200:
                successor_data = response.json().get("all_songs", {})
                all_songs.update(successor_data)  # Merge data from successor
        except Exception as e:
            print(f"Error forwarding wildcard query to {successor_ip}:{successor_port}: {e}")

        return all_songs

    def delete(self, key):
        # Check if i am responsible for the key
        key_hash = self.compute_hash(key)
        if self.is_responsible(key_hash):
            if key in self.data_store:
                del self.data_store[key]
                # Build the final JSON response for a successful delete
                return {
                    "result": True,
                    "message": f"Key '{key}' deleted from node {self.ip}",
                    "data_store": self.data_store,
                    "ip": self.ip
                }
            else:
                # Key not found on this node
                return {
                    "result": False,
                    "error": f"Key '{key}' not found on node {self.ip}",
                    "ip": self.ip
                }
        else:
            # Forward the request to the successor
            successor_ip = self.successor.get("ip")
            successor_port = self.successor.get("port")
            if successor_ip == "0.0.0.0": 
                #
                # ALERT: In AWS this will not work
                # We will want: successor_ip = self.bootstrap_ip
                #
                successor_ip = self.bootstrap_ip
            url = f"http://{successor_ip}:{successor_port}/delete"
            try:
                print(f"[{self.ip}:{self.port}] Forwarding delete request for key '{key}' (hash: {key_hash}) to successor {successor_ip}:{successor_port}.")
                response = requests.post(url, json={"key": key})
                return response.json()
            except Exception as e:
                return {
                    "result": False,
                    "error": f"Error forwarding delete to {self.successor_ip}:{self.successor_port} -> {e}",
                    "ip": self.ip
                }

    def join(self, bootstrap_ip, bootstrap_port):
        # Ο κόμβος που δεν είναι bootstrap καλεί αυτή τη μέθοδο για να εισέλθει στο δίκτυο.
        # Στέλνει αίτημα στον bootstrap κόμβο.
        url = f"http://{bootstrap_ip}:{bootstrap_port}/join"
        payload = {'ip': self.ip, 'port': self.port, 'id': self.id}
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                # If node joined the ring update the successor and predecessor pointers
                data = response.json()
                self.successor = data.get('successor')
                self.predecessor = data.get('predecessor')
                print(f"[{self.ip}:{self.port}] Joined network: successor={self.successor}, predecessor={self.predecessor}")
                return True
            else:
                return False
        except Exception as e:
            print("Error joining network:", e)
            return False
        
    def pull_neighbors(self):
            # New method: the node can later pull updated neighbor info from the bootstrap.
            url = f"http://{self.bootstrap_ip}:{self.bootstrap_port}/get_neighbors"
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    data = response.json()
                    self.update_neighbors(data.get('successor'), data.get('predecessor'))
                    print(f"[{self.ip}:{self.port}] Neighbors updated via pull: successor={self.successor}, predecessor={self.predecessor}")
                    return True
                else:
                    print(f"Pull neighbors failed: {response.text}")
                    return False
            except Exception as e:
                print("Error pulling neighbors:", e)
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

