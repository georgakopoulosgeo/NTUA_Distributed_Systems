import hashlib
import requests
import threading
import uuid
# import replication 

class Node:
    def __init__(self, ip, port, is_bootstrap=False, consistency_mode="eventual", replcation_factor=3):
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
        self.replica_store = {}  # New: storage for replicated key-value pairs.
        self.replication_factor = replcation_factor  # Default replication factor k=1 (i.e. no extra copies). Set to 3, 5, etc. as needed.
        self.consistency_mode = consistency_mode

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
        if origin is None:
            # Setup origin info for callback
            request_id = str(uuid.uuid4())
            event = threading.Event()
            self.pending_requests[request_id] = {"event": event, "result": None}
            origin = {"ip": self.ip, "port": self.port, "request_id": request_id}
            print(f"[{self.ip}:{self.port}] Origin request: {origin}")

        key_hash = self.compute_hash(key)
        if self.is_responsible(key_hash):
            # Primary node: insert in own store.
            if key in self.data_store:
                self.data_store[key] += f" | {value}"
                msg = f"Key '{key}' updated at node {self.ip}."
            else:
                self.data_store[key] = value
                msg = f"Key '{key}' inserted at node {self.ip}."
            print(f"[{self.ip}:{self.port}] {msg}")

            final_result = {
                "result": True,
                "message": msg,
                "ip": self.ip,
                "data_store": self.data_store
            }

            # Replication step based on consistency mode
            if self.replication_factor > 1:
                if self.consistency_mode == "linearizability":
                    # Synchronous chain replication
                    replication_count = self.replication_factor - 1
                    ack = self.chain_replicate_insert(key, value, replication_count)
                    if not ack:
                        final_result["result"] = False
                        final_result["message"] += " Chain replication failed."
                else:
                    # Eventual consistency: asynchronous replication
                    threading.Thread(target=self.async_replicate_insert, args=(key, value, self.replication_factor - 1)).start()

            # If this node is the origin, return the final result directly.
            if origin is None or (origin["ip"] == self.ip and origin["port"] == self.port):
                # If the node is the origin, it would typically signal the waiting thread (if you use pending_requests)
                # For simplicity, we return the final result here.
                return final_result
            else:
                # If not the origin, send a callback to the origin node.
                callback_url = f"http://{origin['ip']}:{origin['port']}/insert_response"
                try:
                    requests.post(callback_url, json={
                        "request_id": origin["request_id"],
                        "final_result": final_result
                    }, timeout=2)
                    print(f"[{self.ip}:{self.port}] Insert processed; callback sent to origin {origin['ip']}:{origin['port']}")
                except Exception as e:
                    print(f"Error sending callback: {e}")
                # Return an intermediate response.
                return {"result": True, "message": "Insert processed; callback sent to origin."}

        else:
            # If this node is not responsible, forward the insert request to the successor.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/insert"
            payload = {"key": key, "value": value, "origin": origin}
            try:
                print(f"[{self.ip}:{self.port}] Forwarding insert request for key '{key}' (hash: {key_hash}) to successor {successor_ip}:{successor_port}.")
                requests.post(url, json=payload)
            except Exception as e:
                return {"result": False, "error": f"Forwarding failed: {e}"}
            return {"result": True, "message": "Insert forwarded."}
        

    def chain_replicate_insert(self, key: str, value: str, replication_count: int) -> bool:
        # Synchronously update local store
        self.data_store[key] = value
        print(f"[{self.ip}:{self.port}] (Chain) Stored key '{key}' locally.")

        if replication_count > 0:
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/chain_replicate_insert"
            payload = {
                "key": key,
                "value": value,
                "replication_count": replication_count - 1
            }
            try:
                print(f"[{self.ip}:{self.port}] Forwarding chain replication for key '{key}' to {successor_ip}:{successor_port} with count {replication_count - 1}.")
                response = requests.post(url, json=payload, timeout=2)
                if response.status_code == 200:
                    ack = response.json().get("ack", False)
                    return ack
                else:
                    print(f"Chain replication failed at {successor_ip}:{successor_port}: {response.text}")
                    return False
            except Exception as e:
                print(f"Error in chain replication: {e}")
                return False

        else:
            # We are at the last valid replica in the new chain.
            # Instruct our successor to delete any stale replica of the key.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/replicate_delete"
            payload = {"key": key, "replication_count": 0}
            try:
                print(f"[{self.ip}:{self.port}] Instructing {successor_ip}:{successor_port} to delete stale replica for key '{key}'.")
                requests.post(url, json=payload, timeout=2)
            except Exception as e:
                print(f"Error instructing deletion of stale replica: {e}")


    def async_replicate_insert(self, key: str, value: str, replication_count: int):
    # Store in replica store (update if exists)
        if key in self.replica_store:
            self.replica_store[key] += f" | {value}"
        else:
            self.replica_store[key] = value
        print(f"[{self.ip}:{self.port}] Asynchronously stored replica for key '{key}'.")

        if replication_count > 0:
            # Propagate asynchronously to the successor with a decremented count.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/async_replicate_insert"
            payload = {"key": key, "value": value, "replication_count": replication_count - 1}
            try:
                print(f"[{self.ip}:{self.port}] Forwarding async replication for key '{key}' to {successor_ip}:{successor_port} with count {replication_count - 1}.")
                requests.post(url, json=payload, timeout=2)
            except Exception as e:
                print(f"Error in async replication: {e}")
        else:
            # When replication_count is 0, instruct the successor to delete any stale replica.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/replicate_delete"
            payload = {"key": key, "replication_count": 0}
            try:
                print(f"[{self.ip}:{self.port}] Instructing {successor_ip}:{successor_port} to delete stale replica for key '{key}'.")
                requests.post(url, json=payload, timeout=2)
            except Exception as e:
                print(f"Error instructing deletion of stale replica: {e}")

    '''
    def replicate_insert(self, key: str, value: str, replication_count: int):
        """
        Αυτή η μέθοδος καλείται από τον κόμβο για να αντιγράψει ένα key-value ζεύγος σε άλλους κόμβους.
        """
        self.replica_store[key] = value
        if replication_count > 0:
            # Αν ο replication_count είναι μεγαλύτερος του 0, προωθούμε το key-value ζεύγος στον επόμενο κόμβο.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/replicate_insert"
            payload = {
                "key": key,
                "value": value,
                "replication_count": replication_count - 1
            }
            try:
                print(f"[{self.ip}:{self.port}] Forwarding replication for key '{key}' to {successor_ip}:{successor_port} with count {replication_count - 1}.")
                requests.post(url, json=payload)
            except Exception as e:
                print(f"Error in replication: {e}")
        else:
            # We are at the last valid replica in the new chain.
            # Instruct our successor to delete any stale replica of the key.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/replicate_delete"
            payload = {"key": key, "replication_count": 0}
            try:
                print(f"[{self.ip}:{self.port}] Instructing {successor_ip}:{successor_port} to delete stale replica for key '{key}'.")
                requests.post(url, json=payload, timeout=2)
            except Exception as e:
                print(f"Error instructing deletion of stale replica: {e}")
    '''
                
    def query(self, key: str, origin: dict = None) -> dict:
        key_hash = self.compute_hash(key)
        # If no origin is provided, this node is the original requester.
        if origin is None:
            request_id = str(uuid.uuid4())
            event = threading.Event()
            self.pending_requests[request_id] = {"event": event, "result": None}
            origin = {
                "ip": self.ip,
                "port": self.port,
                "request_id": request_id
            }
        # If this node is responsible for the key...
        if self.is_responsible(key_hash):
            result = {
                "ip": self.ip,
                "key": key,
                "result": self.data_store.get(key, None)
            }
            # If this request was forwarded from another node, call back the origin.
            if not (origin["ip"] == self.ip and origin["port"] == self.port):
                callback_url = f"http://{origin['ip']}:{origin['port']}/query_response"
                try:
                    print(f"[{self.ip}:{self.port}] Query processed; callback sent to origin {origin['ip']}:{origin['port']}")
                    requests.post(callback_url, json={
                        "request_id": origin["request_id"],
                        "final_result": result
                    })
                except Exception as e:
                    print(f"Error sending query callback: {e}")
                return {"result": True, "message": "Query processed; callback sent to origin."}
            else:
                # If this node is the origin, store the final result and signal the waiting event.
                print(f"[{self.ip}:{self.port}] Query processed; final result stored in pending_requests.")
                req_id = origin["request_id"]
                if req_id in self.pending_requests:
                    self.pending_requests[req_id]["result"] = result
                    self.pending_requests[req_id]["event"].set()
                return result
        else:
            # Forward the query to the successor, including the origin info.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            if (successor_ip == '0.0.0.0'):
                successor_ip = self.bootstrap_ip
                successor_port = self.bootstrap_port
            url = f"http://{successor_ip}:{successor_port}/query?key={key}&origin_ip={origin['ip']}&origin_port={origin['port']}&request_id={origin['request_id']}"
            try:
                print(f"[{self.ip}:{self.port}] Forwarding insert request for key '{key}' (hash: {key_hash}) to successor {successor_ip}:{successor_port}.")
                requests.get(url)
            except Exception as e:
                return {"result": False, "error": f"Forwarding query request failed: {e}"}
            return {"result": True, "message": "Query forwarded."}

           
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
    
    def delete(self, key: str, origin: dict = None) -> dict:
        # If origin is None, this node is the original requester
        if origin is None:
            request_id = str(uuid.uuid4())
            event = threading.Event()
            self.pending_requests[request_id] = {"event": event, "result": None}
            origin = {
                "ip": self.ip,
                "port": self.port,
                "request_id": request_id
            }

        key_hash = self.compute_hash(key)
        if self.is_responsible(key_hash):
            if key in self.data_store:
                del self.data_store[key]
                msg = f"Key '{key}' deleted from node {self.ip}."
                final_result = {
                    "result": True,
                    "message": msg,
                    "ip": self.ip,
                    "data_store": self.data_store
                }
            else:
                msg = f"Key '{key}' not found on node {self.ip}."
                final_result = {
                    "result": False,
                    "error": msg,
                    "ip": self.ip
                }

            # Initiate replication deletion if replication is enabled.
            if self.replication_factor > 1:
                replication_count = self.replication_factor - 1
                self.replicate_delete(key, replication_count)

            if not (origin["ip"] == self.ip and origin["port"] == self.port):
                callback_url = f"http://{origin['ip']}:{origin['port']}/delete_response"
                try:
                    print(f"[{self.ip}:{self.port}] Delete processed; callback sent to origin {origin['ip']}:{origin['port']}")
                    requests.post(callback_url, json={
                        "request_id": origin["request_id"],
                        "final_result": final_result
                    })
                except Exception as e:
                    print(f"[{self.ip}:{self.port}] Error sending delete callback: {e}")

                return {"result": True, "message": "Delete processed; callback sent to origin."}
            else:
                print(f"[{self.ip}:{self.port}] Delete processed; final result stored in pending_requests.")
                req_id = origin["request_id"]
                if req_id in self.pending_requests:
                    self.pending_requests[req_id]["result"] = final_result
                    self.pending_requests[req_id]["event"].set()
                return final_result

        else:
            successor_ip = self.successor.get("ip")
            successor_port = self.successor.get("port")
            url = f"http://{successor_ip}:{successor_port}/delete"
            payload = {
                "key": key,
                "origin": origin
            }
            try:
                print(f"[{self.ip}:{self.port}] Forwarding delete request for key '{key}' (hash: {key_hash}) to successor {successor_ip}:{successor_port}.")
                requests.post(url, json=payload)
            except Exception as e:
                return {"result": False, "error": f"Forwarding delete failed: {e}"}
            return {"result": True, "message": "Delete forwarded."}


    def replicate_delete(self, key: str, replication_count: int):
        """
        Remove the key from the replica_store and, if required,
        forward the deletion request to the successor.
        """
        if key in self.replica_store:
            del self.replica_store[key]
            print(f"[{self.ip}:{self.port}] Deleted replica for key '{key}'.")
        else:
            print(f"[{self.ip}:{self.port}] No replica for key '{key}' found to delete.")

        # Forward the deletion replication if further replicas need updating.
        if replication_count > 0:
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/replicate_delete"
            payload = {
                "key": key,
                "replication_count": replication_count - 1
            }
            try:
                print(f"[{self.ip}:{self.port}] Forwarding delete replication for key '{key}' to {successor_ip}:{successor_port} with count {replication_count - 1}.")
                requests.post(url, json=payload, timeout=2)
            except Exception as e:
                print(f"[{self.ip}:{self.port}] Error forwarding delete replication: {e}")


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
                # Incorporate the keys transferred by the successor.
                transferred_data_store = data.get("data_store", {})
                transferred_replica_store = data.get("replica_store", {})

                # Update local stores with transferred keys:
                self.data_store.update(transferred_data_store)
                self.replica_store.update(transferred_replica_store)

                # For each key that was stolen, initiate a new replication chain.
                for key, value in transferred_data_store.items():
                    # Start a new thread so that the new node doesn't block its join.
                    threading.Thread(
                        target=self.async_replicate_insert,
                        args=(key, value, self.replication_factor - 1)
                    ).start()

                print(f"[{self.ip}:{self.port}] Joined network: successor={self.successor}, predecessor={self.predecessor}")
                print(f"[{self.ip}:{self.port}] Updated local data_store with keys: {list(transferred_data_store.keys())}")
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
        1. Notifies only the predecessor and successor to update their neighbor pointers.
        2. Transfers all keys (from data_store) to the successor so that the successor becomes
        the new primary for these keys.
        3. The successor, on absorbing these keys, re-initiates the replication chain, which also
        cleans up any stale replicas from further down the ring.
        """
        if self.is_bootstrap:
            print("Bootstrap node does not depart.")
            return False

        # Notify predecessor: its new successor should be our successor.
        try:
            pred_ip = self.predecessor["ip"]
            pred_port = self.predecessor["port"]
            url = f"http://{pred_ip}:{pred_port}/update_neighbors"
            payload = {
                "successor": self.successor,  # predecessor's successor becomes our successor
                "predecessor": self.predecessor.get("predecessor", {})  # remain unchanged or as applicable
            }
            requests.post(url, json=payload)
            print(f"[{self.ip}:{self.port}] Notified predecessor at {pred_ip}:{pred_port}.")
        except Exception as e:
            print(f"Error updating predecessor: {e}")

        # Notify successor: its new predecessor should be our predecessor.
        try:
            succ_ip = self.successor["ip"]
            succ_port = self.successor["port"]
            url = f"http://{succ_ip}:{succ_port}/update_neighbors"
            payload = {
                "successor": self.successor.get("successor", {}),  # may be updated later by the successor itself
                "predecessor": self.predecessor  # new predecessor for successor becomes our predecessor
            }
            requests.post(url, json=payload)
            print(f"[{self.ip}:{self.port}] Notified successor at {succ_ip}:{succ_port}.")
        except Exception as e:
            print(f"Error updating successor: {e}")

        # Transfer all keys from our data_store (for which we are primary) to our successor.
        try:
            url = f"http://{succ_ip}:{succ_port}/absorb_keys"
            payload = {
                "keys": self.data_store,
                "replication_factor": self.replication_factor
            }
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                print(f"[{self.ip}:{self.port}] Keys transferred to successor {succ_ip}:{succ_port}.")
            else:
                print(f"[{self.ip}:{self.port}] Failed to transfer keys: {response.text}")
        except Exception as e:
            print(f"Error transferring keys to successor: {e}")

        # Clean up our local stores.
        self.data_store.clear()
        self.replica_store.clear()
        print(f"[{self.ip}:{self.port}] Departed gracefully from the ring.")
        return True