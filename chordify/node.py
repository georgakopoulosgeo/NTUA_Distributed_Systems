import hashlib
import requests
import threading
import uuid
# import replication 

class Node:
    def __init__(self, ip, port, is_bootstrap=False, consistency_mode="strong", replication_factor=1):
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
        self.replication_factor = replication_factor  # Default replication factor k=1 (i.e. no extra copies). Set to 3, 5, etc. as needed.
        self.consistency_mode = consistency_mode # Default consistency mode: strong (linearizability). Set to "eventual" for eventual consistency.

    def compute_hash(self, key):
        # Υπολογισμός του SHA1 hash ενός string και επιστροφή ως ακέραιος.
        h = hashlib.sha1(key.encode('utf-8')).hexdigest()
        return int(h, 16)

    def update_neighbors(self, successor, predecessor):
        # Ενημέρωση των δεδομένων για τον successor και τον predecessor.
        self.successor = successor
        self.predecessor = predecessor
    
    def update_replication_consistency(self, replication_factor, consistency):
        # Ενημέρωση του replication factor και του consistency mode.
        self.replication_factor = replication_factor
        self.consistency_mode = consistency

    def is_responsible(self, key_hash: int) -> bool:
        if self.is_bootstrap:
            return key_hash > self.predecessor["id"]
        else:
            return self.predecessor["id"] < key_hash <= self.id



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
            #print(f"[{self.ip}:{self.port}] Origin request: {origin}")

        key_hash = self.compute_hash(key)
        if self.is_responsible(key_hash):
            # Primary node: insert in own store.
            if key in self.data_store:
                self.data_store[key] += f" | {value}"
                msg = f"Key '{key}' updated at node {self.ip}."
            else:
                self.data_store[key] = value
                msg = f"Key '{key}' inserted at node {self.ip}."
            #print(f"[{self.ip}:{self.port}] {msg}")

            final_result = {
                "result": True,
                "message": msg,
                "ip": self.ip,
                "data_store": self.data_store
            }

            # Replication step based on consistency mode
            if self.consistency_mode == "linearizability" and self.replication_factor > 1:
                # Synchronous chain replication
                replication_count = self.replication_factor - 1
                ack = self.chain_replicate_insert(key, value, replication_count)
                if not ack:
                    final_result["result"] = False
                    final_result["message"] += " Chain replication failed."
            else:
                # Eventual consistency: trigger asynchronous replication if needed
                if self.replication_factor > 1:
                    threading.Thread(
                        target=self.async_replicate_insert, 
                        args=(key, value, self.replication_factor - 1)
                    ).start()
                # Always send a callback to signal the completion, regardless of replication_factor
                callback_url = f"http://{origin['ip']}:{origin['port']}/insert_response"
                try:
                    requests.post(callback_url, json={
                        "request_id": origin["request_id"],
                        "final_result": final_result
                    }, timeout=2)
                except Exception as e:
                    print(f"Error sending callback: {e}")
                return {"result": True, "message": "Insert processed; callback sent to origin."}
            # If this node is the origin, return the final result directly.
            if origin["ip"] == self.ip and origin["port"] == self.port:
                return final_result
            else:
                # If not the origin, send a callback to the origin node (already sent in eventual consistency case)
                if self.consistency_mode == "linearizability":
                    callback_url = f"http://{origin['ip']}:{origin['port']}/insert_response"
                    try:
                        requests.post(callback_url, json={
                            "request_id": origin["request_id"],
                            "final_result": final_result
                        }, timeout=2)
                    except Exception as e:
                        print(f"Error sending callback: {e}")
                return {"result": True, "message": "Insert processed; callback sent to origin."}
        else:
            # If this node is not responsible, forward the insert request to the successor.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/insert"
            payload = {"key": key, "value": value, "origin": origin}
            try:
                #print(f"[{self.ip}:{self.port}] Forwarding insert request for key '{key}' (hash: {key_hash}) to successor {successor_ip}:{successor_port}.")
                requests.post(url, json=payload)
            except Exception as e:
                return {"result": False, "error": f"Forwarding failed: {e}"}
            #return {"result": True, "message": "Insert forwarded."}
        

    def chain_replicate_insert(self, key: str, value: str, replication_count: int) -> bool:
        # Synchronously update local store
        self.data_store[key] = value
        #print(f"[{self.ip}:{self.port}] (Chain) Stored key '{key}' locally.")

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
                #print(f"[{self.ip}:{self.port}] Forwarding chain replication for key '{key}' to {successor_ip}:{successor_port} with count {replication_count}.")
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
                #print(f"[{self.ip}:{self.port}] Instructing {successor_ip}:{successor_port} to delete stale replica for key '{key}'.")
                requests.post(url, json=payload, timeout=2)
            except Exception as e:
                print(f"Error instructing deletion of stale replica: {e}")
            return True # Maybe not necessary, but for clarity.


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
                
    def query(self, key: str, origin: dict = None, chain_count: int = None) -> dict:
        # 1. If no origin is provided, this node is the original requester
        if origin is None:
            request_id = str(uuid.uuid4())
            event = threading.Event()
            self.pending_requests[request_id] = {"event": event, "result": None}
            origin = {"ip": self.ip, "port": self.port, "request_id": request_id}

        key_hash = self.compute_hash(key)

        # 2. We have to find the responsible node for the key. If not responsible, forward.
        # In order to find it we use the chain_count parameter.
        if chain_count is None:
            if not self.is_responsible(key_hash):
                # Not responsible -> forward around the ring unchanged (chain_count stays None).
                successor_ip = self.successor["ip"]
                successor_port = self.successor["port"]
                url = (
                    f"http://{successor_ip}:{successor_port}/query"
                    f"?key={key}&origin_ip={origin['ip']}&origin_port={origin['port']}"
                    f"&request_id={origin['request_id']}"
                )
                # No chain_count in URL => remains None
                print(f"[{self.ip}:{self.port}] Ring-based forward for key '{key}' to {successor_ip}:{successor_port}.")
                try:
                    requests.get(url, timeout=3)
                except Exception as e:
                    return {"result": False, "error": f"Ring-based forward error: {e}"}
                return {"result": True, "message": "Ring-based query forwarded."}
            else:
                # We are responsible -> 'head' of the chain for linearizability
                if self.consistency_mode == "linearizability":
                    # Start chain replication pass
                    chain_count = self.replication_factor - 1
                    return self._handle_query_linearizability(key, origin, chain_count)
                else:
                    # Eventual consistency -> just do local read
                    return self._handle_query_eventual(key, origin)

        # 3. If chain_count is not None, we've already located the head and are in the chain pass
        if self.consistency_mode == "linearizability":
            # Continue chain replication with this helper func
            return self._handle_query_linearizability(key, origin, chain_count)
        else:
            # Eventual consistency -> just do local read
            return self._return_local_or_callback(key, origin)


    def _handle_query_linearizability(self, key: str, origin: dict, chain_count: int) -> dict:
        if chain_count > 0:
            # Not tail yet -> forward to successor
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = (
                f"http://{successor_ip}:{successor_port}/query"
                f"?key={key}&origin_ip={origin['ip']}&origin_port={origin['port']}"
                f"&request_id={origin['request_id']}&chain_count={chain_count - 1}"
            )
            print(f"[{self.ip}:{self.port}] Chain-mode forward for '{key}' to {successor_ip}:{successor_port}, chain_count={chain_count - 1}")
            try:
                requests.get(url, timeout=3)
            except Exception as e:
                return {"result": False, "error": f"Chain-mode forward error: {e}"}
            return {"result": True, "message": "Chain query forwarded."}
        else:
            # When chain_count reaches 0, we are the tail -> return local or callback
            return self._return_local_or_callback(key, origin)


    def _return_local_or_callback(self, key: str, origin: dict) -> dict:
        local_value = self.data_store.get(key, None)
        result = {
            "ip": self.ip,
            "key": key,
            "result": local_value
        }

        # If we are NOT the origin, we must POST a callback to the origin
        if not (origin["ip"] == self.ip and origin["port"] == self.port):
            callback_url = f"http://{origin['ip']}:{origin['port']}/query_response"
            print(f"[{self.ip}:{self.port}] Returning final read to origin {origin['ip']}:{origin['port']}")
            try:
                requests.post(callback_url, json={
                    "request_id": origin["request_id"],
                    "final_result": result
                }, timeout=3)
            except Exception as e:
                print(f"Error sending query callback: {e}")
            return {"result": True, "message": "Query tail responded to origin."}
        else:
            # We are the origin -> store final result in pending_requests
            req_id = origin["request_id"]
            if req_id in self.pending_requests:
                self.pending_requests[req_id]["result"] = result
                self.pending_requests[req_id]["event"].set()
            return result
    
            

           
    def query_wildcard(self, origin=None):
        """
        Aggregates all key-value pairs in the DHT ring for a wildcard '*' query.
        The 'origin' parameter is a string (ip:port) set by the initiating node.
        Aggregation stops when the query reaches back to the origin.
        """
        my_id = f"{self.ip}:{self.port}"
        if origin is None:
            origin = my_id

        print(f"[{self.ip}:{self.port}] Processing wildcard query. Origin: {origin}")

        # Determine successor identifier.
        successor_identifier = f"{self.successor.get('ip')}:{self.successor.get('port')}"
        # If the successor is the origin, we've reached the end of the ring.
        if successor_identifier == origin:
            print(f"[{self.ip}:{self.port}] Wildcard query reached the end of the ring. Returning local data.")
            return self.data_store

        # Otherwise, forward the wildcard query to the successor.
        url = f"http://{self.successor['ip']}:{self.successor['port']}/query?key=*&origin={origin}"
        try:
            print(f"[{self.ip}:{self.port}] Forwarding wildcard query to {successor_identifier} with origin {origin}.")
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                successor_data = response.json().get("all_songs", {})
            else:
                print(f"[{self.ip}:{self.port}] Error: Received status code {response.status_code} from successor.")
                successor_data = {}
        except Exception as e:
            print(f"[{self.ip}:{self.port}] Error forwarding wildcard query: {e}")
            successor_data = {}

        # Merge current node's data with the data received from the successor.
        merged_data = {}
        merged_data.update(self.data_store)
        merged_data.update(successor_data)
        return merged_data
    
    def delete(self, key: str, origin: dict = None):
        """
        Delete a key (song) from the node.
        If origin is None, this node is the origin and sets up a pending request.
        Otherwise, the request is being forwarded.
        """
        if origin is None:
            # Setup origin info for callback
            request_id = str(uuid.uuid4())
            event = threading.Event()
            self.pending_requests[request_id] = {"event": event, "result": None}
            origin = {"ip": self.ip, "port": self.port, "request_id": request_id}
            print(f"[{self.ip}:{self.port}] Origin delete request: {origin}")

        key_hash = self.compute_hash(key)
        if self.is_responsible(key_hash):
            # Responsible node: attempt deletion in own data_store
            if key in self.data_store:
                del self.data_store[key]
                msg = f"Key '{key}' deleted from node {self.ip}."
                result = True
            else:
                msg = f"Key '{key}' not found on node {self.ip}."
                result = False
            final_result = {
                "result": result,
                "message": msg,
                "ip": self.ip,
                "data_store": self.data_store
            }
            print(f"[{self.ip}:{self.port}] {msg}")

            # Propagate deletion to replicas if needed
            if self.replication_factor > 1:
                if self.consistency_mode == "linearizability":
                    replication_count = self.replication_factor - 1
                    ack = self.chain_replicate_delete(key, replication_count)
                    if not ack:
                        final_result["result"] = False
                        final_result["message"] += " Chain replication deletion failed."
                        print(f"[{self.ip}:{self.port}] Chain replication deletion failed for key '{key}'.")
                else:
                    threading.Thread(target=self.async_replicate_delete, args=(key, self.replication_factor - 1)).start()

            # Return or callback the final result
            if origin is None or (origin["ip"] == self.ip and origin["port"] == self.port):
                return final_result
            else:
                callback_url = f"http://{origin['ip']}:{origin['port']}/delete_response"
                try:
                    requests.post(callback_url, json={
                        "request_id": origin["request_id"],
                        "final_result": final_result
                    }, timeout=2)
                    print(f"[{self.ip}:{self.port}] Delete processed; callback sent to origin {origin['ip']}:{origin['port']}")
                except Exception as e:
                    print(f"Error sending delete callback: {e}")
                return {"result": True, "message": "Delete processed; callback sent to origin."}
        else:
            # Not responsible: forward the delete request to the successor.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/delete"
            payload = {"key": key, "origin": origin}
            try:
                print(f"[{self.ip}:{self.port}] Forwarding delete request for key '{key}' to successor {successor_ip}:{successor_port}.")
                requests.post(url, json=payload)
            except Exception as e:
                return {"result": False, "error": f"Forwarding deletion failed: {e}"}
            return {"result": True, "message": "Delete forwarded."}

    def chain_replicate_delete(self, key: str, replication_count: int) -> bool:
        """
        Perform synchronous (chain) deletion replication.
        Delete the key from the local store and, if more replicas are needed,
        forward the delete request to the successor.
        """
        if key in self.data_store:
            del self.data_store[key]
            print(f"[{self.ip}:{self.port}] (Chain) Deleted key '{key}' locally.")
        else:
            print(f"[{self.ip}:{self.port}] (Chain) Key '{key}' not found locally for deletion.")
        
        if replication_count > 0:
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/chain_replicate_delete"
            payload = {"key": key, "replication_count": replication_count - 1}
            try:
                print(f"[{self.ip}:{self.port}] Forwarding chain deletion for key '{key}' to {successor_ip}:{successor_port} with count {replication_count}.")
                response = requests.post(url, json=payload, timeout=2)
                if response.status_code == 200:
                    ack = response.json().get("ack", False)
                    return ack
                else:
                    print(f"Chain deletion failed at {successor_ip}:{successor_port}: {response.text}")
                    return False
            except Exception as e:
                print(f"Error in chain replication deletion: {e}")
                return False
        else:
            # Instruct successor to delete any stale replica when count reaches 0.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/replicate_delete"
            payload = {"key": key, "replication_count": 0}
            try:
                print(f"[{self.ip}:{self.port}] Instructing {successor_ip}:{successor_port} to delete stale replica for key '{key}'.")
                requests.post(url, json=payload, timeout=2)
            except Exception as e:
                print(f"Error instructing deletion of stale replica: {e}")
            return True  # Assuming deletion of stale replica succeeds

    def async_replicate_delete(self, key: str, replication_count: int):
        """
        Perform asynchronous deletion replication.
        Delete the key from the replica store and propagate asynchronously.
        """
        if key in self.replica_store:
            del self.replica_store[key]
            print(f"[{self.ip}:{self.port}] Asynchronously deleted replica for key '{key}'.")
        else:
            print(f"[{self.ip}:{self.port}] Asynchronously: Key '{key}' not found in replica store.")

        if replication_count > 0:
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/async_replicate_delete"
            payload = {"key": key, "replication_count": replication_count - 1}
            try:
                print(f"[{self.ip}:{self.port}] Forwarding async deletion for key '{key}' to {successor_ip}:{successor_port} with count {replication_count - 1}.")
                requests.post(url, json=payload, timeout=2)
            except Exception as e:
                print(f"Error in async deletion replication: {e}")
        else:
            # When no more asynchronous replication is needed, ensure stale replicas are cleaned.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/replicate_delete"
            payload = {"key": key, "replication_count": 0}
            try:
                print(f"[{self.ip}:{self.port}] Instructing {successor_ip}:{successor_port} to delete stale replica for key '{key}' after async deletion.")
                requests.post(url, json=payload, timeout=2)
            except Exception as e:
                print(f"Error instructing deletion of stale replica: {e}")

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
                #Update replication factor and consistency mode
                self.replication_factor = data.get("replication_factor")
                self.consistency_mode = data.get("consistency")

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

                print(f"[{self.ip}:{self.port}] Joined network")
                print(f"[{self.ip}:{self.port}] Updated local data_store with keys: {list(transferred_data_store.keys())}")
                return True
            else:
                return False
        except Exception as e:
            print("Error joining network:", e)
            return False
        
    def pull_neighbors(self):
        # 
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
        1. Notifies the predecessor and successor to update their neighbor pointers.
        2. Transfers all keys (from data_store) to the successor.
        3. Cleans up local data.
        4. Notifies the bootstrap to remove this node from the ring.
        """
        if self.is_bootstrap:
            print("Bootstrap node does not depart.")
            return False

        # Notify predecessor: update its successor pointer.
        try:
            pred_ip = self.predecessor["ip"]
            pred_port = self.predecessor["port"]
            url = f"http://{pred_ip}:{pred_port}/update_neighbors"
            payload = {
                "successor": self.successor,  # Predecessor's new successor becomes our successor.
                "predecessor": self.predecessor.get("predecessor", {})
            }
            requests.post(url, json=payload)
            print(f"[{self.ip}:{self.port}] Notified predecessor at {pred_ip}:{pred_port}.")
        except Exception as e:
            print(f"Error updating predecessor: {e}")

        # Notify successor: update its predecessor pointer.
        try:
            succ_ip = self.successor["ip"]
            succ_port = self.successor["port"]
            url = f"http://{succ_ip}:{succ_port}/update_neighbors"
            payload = {
                "successor": self.successor.get("successor", {}),
                "predecessor": self.predecessor  # New predecessor for successor becomes our predecessor.
            }
            requests.post(url, json=payload)
            print(f"[{self.ip}:{self.port}] Notified successor at {succ_ip}:{succ_port}.")
        except Exception as e:
            print(f"Error updating successor: {e}")

        # Transfer all keys from our data_store (for which we are primary) to the successor.
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

        # Clean up local stores.
        self.data_store.clear()
        self.replica_store.clear()
        print(f"[{self.ip}:{self.port}] Departed gracefully from the ring.")

        # NEW STEP: Notify the bootstrap to remove this node from the ring.
        try:
            remove_url = f"http://{self.bootstrap_ip}:{self.bootstrap_port}/remove_node"
            data = {
                "id": self.id,
                "ip": self.ip,
                "port": self.port
            }
            requests.post(remove_url, json=data)
            print(f"[{self.ip}:{self.port}] Informed bootstrap to remove me from the ring.")
        except Exception as e:
            print(f"Error informing bootstrap to remove node: {e}")

        return True