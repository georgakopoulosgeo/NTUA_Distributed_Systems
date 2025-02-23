import hashlib
import requests
import threading
import uuid

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
        self.pending_requests = {} # Κρατάει τα αιτήματα που περιμένουν απάντηση


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



    def insert(self, key: str, value: str, origin: dict = None):
        """
        If origin is None, we treat this node as the 'origin'.
        If not None, we forward or respond with a callback.
        """
        # If there's no origin, this node is the origin node
        if origin is None:
            request_id = str(uuid.uuid4())
            event = threading.Event()
            self.pending_requests[request_id] = {"event": event, "result": None}
            origin = {
                "ip": self.ip,
                "port": self.port,
                "request_id": request_id
            }
        # Now do normal Chord logic
        key_hash = self.compute_hash(key)

        if self.is_responsible(key_hash):
            # Responsible node -> do the actual insert
            if key in self.data_store:
                self.data_store[key] += f" | {value}"
                msg = f"Key '{key}' updated at node {self.ip}."
            else:
                self.data_store[key] = value
                msg = f"Key '{key}' inserted at node {self.ip}."

            final_result = {
                "result": True,
                "message": msg,
                "ip": self.ip,
                "data_store": self.data_store
            }

            # If I'm not the origin, callback to the origin with final_result
            if not (origin["ip"] == self.ip and origin["port"] == self.port):
                print(f"Insert processed; callback sent to origin {origin['ip']}:{origin['port']}")
                callback_url = f"http://{origin['ip']}:{origin['port']}/insert_response"
                try:
                    requests.post(callback_url, json={
                        "request_id": origin["request_id"],
                        "final_result": final_result
                    })
                except Exception as e:
                    print(f"Error sending callback: {e}")

                # Return something minimal, because the real result goes via callback
                return {"result": True, "message": "Insert processed; callback sent to origin."}
            else:
                # If I AM the origin, set the final result in pending_requests
                req_id = origin["request_id"]
                if req_id in self.pending_requests:
                    self.pending_requests[req_id]["result"] = final_result
                    self.pending_requests[req_id]["event"].set()
                return final_result
        else:
            # Not responsible -> forward
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/insert"
            payload = {
                "key": key,
                "value": value,
                "origin": origin
            }
            try:
                print(f"[{self.ip}:{self.port}] Forwarding insert request for key '{key}' (hash: {key_hash}) to successor {successor_ip}:{successor_port}.")
                requests.post(url, json=payload)
            except Exception as e:
                return {"result": False, "error": f"Forwarding failed: {e}"}
            return {"result": True, "message": "Insert forwarded."}
        
    def query(self, key: str) -> dict:
        key_hash = self.compute_hash(key)

        # If this node is responsible, return only the final response
        if self.is_responsible(key_hash):
            return {
                "ip": self.ip,
                "key": key,
                "result": self.data_store.get(key, None)
            }

        # Forward the request to the successor
        successor_ip = self.successor.get("ip")
        successor_port = self.successor.get("port")

        if successor_ip == "0.0.0.0":
            successor_ip = self.bootstrap_ip  # Use bootstrap if necessary

        url = f"http://{successor_ip}:{successor_port}/query?key={key}"

        try:
            response = requests.get(url)
            response_data = response.json()
            
            # Instead of wrapping the response in another layer, return it as is
            return response_data if isinstance(response_data, dict) else {"error": "Invalid response format"}

        except Exception as e:
            return {
                "key": key,
                "result": None,
                "ip": None,
                "error": f"Forwarding query request failed: {e}"
            }

           
    def query_wildcard(self, origin=None, collected_data=None):
        """
        Handles wildcard '*' queries by aggregating all songs from the DHT ring.
        Prevents infinite loops by stopping when the query reaches the origin node again.
        """
        if collected_data is None:
            collected_data = {}  # Initialize only once

        if origin is None:
            origin = f"{self.ip}:{self.port}"  # Set origin only for the first node

        print(f"[{self.ip}:{self.port}] Collecting all keys. Origin: {origin}")

        # Merge this node's data into the collected dictionary
        collected_data.update(self.data_store)

        successor_ip = self.successor.get("ip")
        successor_port = self.successor.get("port")
        successor_identifier = f"{successor_ip}:{successor_port}"

        # Stop forwarding when reaching the original requester
        if successor_identifier == origin:
            print(f"[{self.ip}:{self.port}] Wildcard query completed, returning collected data.")
            return collected_data  # Stop recursion here

        # Forward query to the next node in the ring
        url = f"http://{successor_ip}:{successor_port}/query?key=*"
        try:
            print(f"[{self.ip}:{self.port}] Forwarding wildcard query '*' to {successor_identifier}.")
            response = requests.get(url)
            if response.status_code == 200:
                successor_data = response.json().get("all_songs", {})
                collected_data.update(successor_data)  # Merge data from successor
        except Exception as e:
            print(f"Error forwarding wildcard query to {successor_ip}:{successor_port}: {e}")

        return collected_data
    
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

