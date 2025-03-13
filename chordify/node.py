import hashlib
from flask import current_app
import requests
import threading
import uuid
import time

# This class represents a node in the DHT ring.
# Here we implement the main methods for the node to interact with the ring.
# The node can insert, query, delete, join and depart from the ring.
# We also implemented helper methods for replication and consistency, as well as methods for taking node info or updating its fields. 

class Node:
    def __init__(self, ip, port, is_bootstrap=False, consistency_mode="strong", replication_factor=1):
        self.ip = ip #IP address of the node
        self.port = port #Port number of the node
        self.is_bootstrap = is_bootstrap #Boolean value to check if the node is a bootstrap node
        self.id = 0 if is_bootstrap else self.compute_hash(f"{self.ip}:{self.port}") #Unique ID of the node
        self.successor = {}  #Successor node
        self.predecessor = {} #Predecessor node
        self.data_store = {}   #Data store for the node
        self.pending_requests = {} #Pending requests for the node
        self.pending_requests_lock = threading.Lock() #Lock for pending requests
        self.replica_store = {} #Replica store for the node
        self.replication_factor = replication_factor #Replication factor for the node
        self.consistency_mode = consistency_mode #Consistency mode for the node

    # Compute the hash of a keys
    def compute_hash(self, key):
        h = hashlib.sha1(key.encode('utf-8')).hexdigest()
        return int(h, 16)
    
    # Update the node's ID
    def update_local_pointers(self, ring):
        for node_info in ring:
            print(f"[{self.ip}:{self.port}] Checking node: {node_info}")
            if node_info['id'] == self.id:
                self.successor = node_info["successor"]
                self.predecessor = node_info["predecessor"]
                print(f"[{self.ip}:{self.port}] Updated local pointers: successor={self.successor}, predecessor={self.predecessor}")
                return
        print(f"[{self.ip}:{self.port}] Warning: Could not update local pointers from the ring.")


    # Update the node's successor and predecessor
    def update_neighbors(self, successor, predecessor):
        # If successor or predecessor are empty dictionaries, do not update them.
        # Might occur when the node is the only one in the ring or during a depart of a node.
        if successor: 
            self.successor = successor
        if predecessor:
            self.predecessor = predecessor
    
    # Update the node's consistency mode and replication factor
    def update_replication_consistency(self, replication_factor, consistency):
        self.replication_factor = replication_factor
        self.consistency_mode = consistency

    # Check if the node is responsible for a key
    def is_responsible(self, key_hash: int) -> bool:
        if self.is_bootstrap:
            return key_hash > self.predecessor["id"]
        else:
            return self.predecessor["id"] < key_hash <= self.id

    # Main method for inserting a key-value pair into the DHT.
    def insert(self, key: str, value: str, origin: dict = None) -> (dict, str):  # type: ignore
        if origin is None:
            # If there is no origin, this node is the original requester.
            # Initialize a request_id and event for the pending request.
            request_id = str(uuid.uuid4())
            event = threading.Event()
            with self.pending_requests_lock:
                self.pending_requests[request_id] = {"event": event, "result": None}
            origin = {"ip": self.ip, "port": self.port, "request_id": request_id}
            is_origin = True
            print(f"[{self.ip}:{self.port}] Origin request: {origin}")
        else:
            # If there is an origin, this node is forwarding the request, use the provided request_id.
            is_origin = False
            request_id = origin.get("request_id")

        key_hash = self.compute_hash(key)
        if self.is_responsible(key_hash):
            # If the node is responsible for the key, insert it locally.
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

            if self.consistency_mode == "linearizability" and self.replication_factor > 1:
                # If the consistency mode is linearizability, start chain replication using the helper method.
                replication_count = self.replication_factor - 1
                self.chain_replicate_insert(key, value, replication_count, origin, final_result)
            else:
                # If the consistency mode is eventual consistency, replicate asynchronously and callback immediately.
                if self.replication_factor > 1:
                    threading.Thread(
                        target=self.async_replicate_insert, 
                        args=(key, value, self.replication_factor - 1)
                    ).start()
                # Also, if the consistency mode is linearizability and the replication factor is 0, the callback is sent here.
                callback_url = f"http://{origin['ip']}:{origin['port']}/insert_response"
                try:
                    requests.post(callback_url, json={
                        "request_id": origin["request_id"],
                        "final_result": final_result
                    }, timeout=2)
                except Exception as e:
                    print(f"Error sending callback: {e}")
                if not is_origin:
                    # if this node is not the origin, return the final result immediately, without waiting for the callback.
                    # We no longer need the request_id in the pending_requests dict. 
                    return (final_result, None)

            if origin["ip"] == self.ip and origin["port"] == self.port:
                # If this node is the origin, return the final result immediately, with the request_id.
                return (final_result, request_id)
            else:
                # Otherwise, indicate that the insert was processed; the callback will be sent from the chain.
                return ({"result": True, "message": "Insert processed; callback will be sent from chain replication."}, request_id)
        else:
            # If this node is not responsible, forward the insert request to the successor.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/insert"
            payload = {"key": key, "value": value, "origin": origin}
            try:
                requests.post(url, json=payload)
            except Exception as e:
                return ({"result": False, "error": f"Forwarding failed: {e}"}, request_id)
            return ({"result": True, "message": "Insert forwarded."}, request_id)

    # Performs synchronous chain replication for linearizability.
    def chain_replicate_insert(self, key: str, value: str, replication_count: int, origin: dict, final_result: dict) -> None:
        if key not in self.data_store: # The node that is responsible for the key should not have a stale replica.
            if key in self.replica_store:
                self.replica_store[key] += f" | {value}"
            else:
                self.replica_store[key] = value
        print(f"[{self.ip}:{self.port}] (Chain) Stored key '{key}' locally.")

        if replication_count > 0:
            # Forward the chain replication request.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/chain_replicate_insert"
            payload = {
                "key": key,
                "value": value,
                "replication_count": replication_count - 1,
                "origin": origin,
                "final_result": final_result
            }
            try:
                requests.post(url, json=payload, timeout=20)
            except Exception as e:
                print(f"Error in chain replication: {e}")
        else:
            # Last replica in the chain: assign commit sequence and send callback to the origin.
            if not hasattr(self, "commit_seq_per_key"):
                self.commit_seq_per_key = {}
            if key not in self.commit_seq_per_key:
                self.commit_seq_per_key[key] = 0
            self.commit_seq_per_key[key] += 1
            final_result["commit_seq"] = self.commit_seq_per_key[key]
            # Last replica in the chain: send callback to the origin node. (Characteristic of Linearizability) 
            callback_url = f"http://{origin['ip']}:{origin['port']}/insert_response"
            try:
                requests.post(callback_url, json={
                    "request_id": origin["request_id"],
                    "final_result": final_result
                }, timeout=2)
            except Exception as e:
                print(f"Error sending callback: {e}")
            print(f"[{self.ip}:{self.port}] Chain replication for key '{key}' completed.")

    # Performs asynchronous replication for eventual consistency.
    def async_replicate_insert(self, key: str, value: str, replication_count: int):
        if "ip" not in self.successor:
            print(f"[{self.ip}:{self.port}] Error: No successor found for async replication.")
            return False

        # time.sleep(0.3)  # Simulate a delay in the replication process.
        if key not in self.data_store: # The node that is responsible for the key should not have a stale replica.
            if key in self.replica_store:
                current_value = self.replica_store[key]
                if value in current_value.split(" | "):
                    # Already applied this update; do nothing.
                    pass
                else:
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
                #print(f"[{self.ip}:{self.port}] Forwarding async replication for key '{key}' to {successor_ip}:{successor_port} with count {replication_count - 1}.")
                requests.post(url, json=payload, timeout=2)
            except Exception as e:
                print(f"Error in async replication: {e}")
        else:
            print(f"[{self.ip}:{self.port}] Asynchronous replication for key '{key}' completed.")

    # Main method for querying a key-value pair from the DHT.
    def query(self, key: str, origin: dict = None, chain_count: int = None) -> (dict, str): # type: ignore
        # 1. If no origin is provided, this node is the original requester
        if origin is None:
            request_id = str(uuid.uuid4())
            event = threading.Event()
            with self.pending_requests_lock:
                self.pending_requests[request_id] = {"event": event, "result": None}
            origin = {"ip": self.ip, "port": self.port, "request_id": request_id}
            is_origin = True
            print(f"[{self.ip}:{self.port}] Origin query request: {origin}")
        else:
            is_origin = False
            request_id = origin.get("request_id")

        key_hash = self.compute_hash(key)

        # 2. We have to find the responsible node for the key. If not responsible, forward.
        # In order to find it we use the chain_count parameter.
        if chain_count is None:
            if self.consistency_mode == "linearizability":
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
                        return ({"result": False, "error": f"Ring-based forward error: {e}"}, request_id)
                    return ({"result": True, "message": "Ring-based query forwarded."}, request_id)
                else:
                    # We are responsible -> 'head' of the chain for linearizability
                    chain_count = self.replication_factor - 1
                    return self._handle_query_linearizability(key, origin, chain_count)
            else:
                # Case of eventual consistency
                return self._handle_query_eventual(key, origin)

        # 3. If chain_count is not None, we've already located the head and are in the chain pass
        if self.consistency_mode == "linearizability":
            # Continue chain replication with this helper func
            return self._handle_query_linearizability(key, origin, chain_count)
        else:
            # Eventual consistency -> just do local read
            return self._return_local_or_callback(key, origin)

    # Helper method for handling query requests in linearizability mode.
    def _handle_query_linearizability(self, key: str, origin: dict, chain_count: int) -> (dict, str): # type: ignore
        req_id = origin["request_id"]
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
                return ({"result": False, "error": f"Chain-mode forward error: {e}"}, req_id)
            return ({"result": True, "message": "Chain query forwarded."}, req_id)
        else:
            # When chain_count reaches 0, we are the tail -> return local or callback
            return self._return_local_or_callback(key, origin)
    
    # Helper method for handling query requests in eventual consistency mode.
    def _handle_query_eventual(self, key: str, origin: dict) -> (dict, str): # type: ignore
        # Check if the key exists in either the primary or replica store.
        req_id = origin["request_id"]
        if key in self.data_store or key in self.replica_store:
                return self._return_local_or_callback(key, origin)
        key_hash = self.compute_hash(key)
        if self.is_responsible(key_hash):
            # Key not found locally, but this node is responsible. So the key does not exist.
            print(f"[{self.ip}:{self.port}] Eventual consistency: key '{key}' not found locally.")
            return self._return_local_or_callback(key, origin)
        else:
            # Not found locally; forward the query to the successor.
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = (
                f"http://{successor_ip}:{successor_port}/query"
                f"?key={key}&origin_ip={origin['ip']}&origin_port={origin['port']}"
                f"&request_id={origin['request_id']}"
            )
            print(f"[{self.ip}:{self.port}] Eventual consistency: key '{key}' not found locally. Forwarding to {successor_ip}:{successor_port}.")
            try:
                requests.get(url, timeout=3)
            except Exception as e:
                return ({"result": False, "error": f"Eventual consistency forward error: {e}"}, req_id)
            return ({"result": True, "message": "Eventual query forwarded."}, req_id)

    # Helper method for returning the local result or sending a callback.
    def _return_local_or_callback(self, key: str, origin: dict) -> (dict, str): # type: ignore
        local_value = self.data_store.get(key, self.replica_store.get(key, None))
        responding_node = f"{self.ip}:{self.port}"
        result = {
            "Result from": responding_node,
            "key": key,
            "result": local_value
        }

         # If the key is not found locally, immediately return a "not found" result.
        if local_value is None:
            no_result = {"result": False, "error": "Song not found", "key": key}
            req_id = origin["request_id"]
            # If this node is the origin, set the pending request result immediately.
            if origin["ip"] == self.ip and origin["port"] == self.port:
                with self.pending_requests_lock:
                    if req_id in self.pending_requests:
                        self.pending_requests[req_id]["result"] = no_result
                        self.pending_requests[req_id]["event"].set()
                return (no_result, req_id)
            else:
                # If not the origin, send a callback immediately.
                callback_url = f"http://{origin['ip']}:{origin['port']}/query_response"
                try:
                    requests.post(callback_url, json={"request_id": req_id, "final_result": no_result}, timeout=3)
                except Exception as e:
                    print(f"Error sending callback: {e}")
                return (no_result, req_id)

        # If we are NOT the origin, we must POST a callback to the origin
        if not (origin["ip"] == self.ip and origin["port"] == self.port):
            callback_url = f"http://{origin['ip']}:{origin['port']}/query_response"
            print(f"[{self.ip}:{self.port}] Returning final read to origin {origin['ip']}:{origin['port']}")
            req_id = origin["request_id"]
            try:
                requests.post(callback_url, json={
                    "request_id": origin["request_id"],
                    "final_result": result
                }, timeout=3)
            except Exception as e:
                print(f"Error sending query callback: {e}")
            return ({"result": True, "message": "Query tail responded to origin."}, req_id)
        else:
            # We are the origin -> store final result in pending_requests
            req_id = origin["request_id"]
            with self.pending_requests_lock:
                if req_id in self.pending_requests:
                    self.pending_requests[req_id]["result"] = result
                    self.pending_requests[req_id]["event"].set()
            return (result, req_id)
    
            
    # Corner case: If we need all the songs in the DHT ring, we can use a wildcard query.
    # Go to each node in the ring and collect all the songs.
    def query_wildcard(self, origin=None):
        my_id = f"{self.ip}:{self.port}"
        if origin is None:
            origin = my_id

        print(f"[{my_id}] Processing wildcard query. Origin: {origin}")

        # Gather local songs from both primary and replica stores.
        local_songs = {}
        local_songs.update(self.data_store)
        local_songs.update(self.replica_store)
        # Create a result dict mapping this node to its songs.
        result = {my_id: local_songs}

        # Determine successor identifier.
        successor_identifier = f"{self.successor.get('ip')}:{self.successor.get('port')}"
        # If we've completed a full circle, return our result.
        if successor_identifier == origin:
            print(f"[{my_id}] Wildcard query reached the end of the ring. Returning local data.")
            return result

        # Otherwise, forward the wildcard query to the successor.
        url = f"http://{self.successor['ip']}:{self.successor['port']}/query?key=*&origin={origin}"
        try:
            print(f"[{my_id}] Forwarding wildcard query to {successor_identifier} with origin {origin}.")
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                successor_data = response.json().get("all_songs", {})
            else:
                print(f"[{my_id}] Error: Received status code {response.status_code} from successor.")
                successor_data = {}
        except Exception as e:
            print(f"[{my_id}] Error forwarding wildcard query: {e}")
            successor_data = {}

    # Merge our own result with the data returned from the successor.
        result.update(successor_data)
        return result

    # Main method for deleting a key-value pair from the DHT.
    def delete(self, key: str, origin: dict = None):
        if origin is None:
            # This node is the origin
            request_id = str(uuid.uuid4())
            event = threading.Event()
            self.pending_requests[request_id] = {"event": event, "result": None}
            origin = {"ip": self.ip, "port": self.port, "request_id": request_id}
            print(f"[{self.ip}:{self.port}] Origin delete request: {origin}")

        key_hash = self.compute_hash(key)

        if self.is_responsible(key_hash):
            # We are the responsible node => remove from our data_store
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

            # Now replicate the delete to other nodes
            if self.replication_factor > 1:
                if self.consistency_mode == "linearizability":
                    # Synchronous chain replication
                    replication_count = self.replication_factor - 1
                    if replication_count > 0:
                        # Forward the chain delete to successor
                        successor_ip = self.successor["ip"]
                        successor_port = self.successor["port"]
                        url = f"http://{successor_ip}:{successor_port}/chain_replicate_delete"
                        payload = {"key": key, "replication_count": replication_count}
                        try:
                            print(f"[{self.ip}:{self.port}] Forwarding chain replication delete for '{key}' to {successor_ip}:{successor_port}.")
                            response = requests.post(url, json=payload, timeout=2)
                            # Check ack
                            ack = (response.status_code == 200 and response.json().get("ack", False))
                            if not ack:
                                final_result["result"] = False
                                final_result["message"] += " Chain replication deletion failed."
                                print(f"[{self.ip}:{self.port}] Chain replication deletion failed for key '{key}'.")
                        except Exception as e:
                            final_result["result"] = False
                            final_result["message"] += f" Chain replication deletion failed: {e}"
                else:
                    # Eventual => async replicate to the next node
                    threading.Thread(target=self.async_replicate_delete, args=(key, self.replication_factor - 1)).start()

            # Callback or return
            if origin is None or (origin["ip"] == self.ip and origin["port"] == self.port):
                # We are the origin and can return directly
                return final_result
            else:
                # Send callback to the origin
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
            # Not responsible => forward to successor
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
        # Perform synchronous chain deletion replication for linearizability.
        # In this approach, replicas store the key in replica_store,
        # so remove it from replica_store here, then forward if needed.
        # Remove from replica_store (because this node is a replica in the chain)
        if key in self.replica_store:
            del self.replica_store[key]
            print(f"[{self.ip}:{self.port}] (Chain) Deleted key '{key}' from replica_store.")
        else:
            print(f"[{self.ip}:{self.port}] (Chain) Key '{key}' not found in replica_store.")
            return False

        # Forward if there are more replicas in the chain
        if replication_count > 0:
            successor_ip = self.successor["ip"]
            successor_port = self.successor["port"]
            url = f"http://{successor_ip}:{successor_port}/chain_replicate_delete"
            payload = {"key": key, "replication_count": replication_count - 1}
            try:
                print(f"[{self.ip}:{self.port}] Forwarding chain deletion for key '{key}' to {successor_ip}:{successor_port} (count={replication_count - 1}).")
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
            return True

    def async_replicate_delete(self, key: str, replication_count: int):
        # Perform asynchronous deletion replication.
        # Delete the key from the replica store and propagate asynchronously.
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
            return True

    def join(self, bootstrap_ip, bootstrap_port):
        # Main method for a node to join the ring.
        # Non bootstrap node joining the ring. Send a POST request to the bootstrap node.
        url = f"http://{bootstrap_ip}:{bootstrap_port}/join"
        payload = {'ip': self.ip, 'port': self.port, 'id': self.id}
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                # After the bootstrap node responds, and has aprroved the join, the node can update its fields.
                data = response.json()
                self.successor = data.get('successor')
                self.predecessor = data.get('predecessor')
                self.replication_factor = data.get("replication_factor")
                self.consistency_mode = data.get("consistency")

                # Store the updated ring for later cleanup logic.
                ring = data.get("ring", [])
                self.ring = ring
                
                # Get transferred primary keys
                transferred_data_store = data.get("data_store", {})
                # And update local store
                self.data_store.update(transferred_data_store)
                
                # For each key that became primary, start a new replication chain.
                for key, value in transferred_data_store.items():
                    threading.Thread(
                        target=self.async_replicate_insert,
                        args=(key, value, self.replication_factor - 1)
                    ).start()
                

                transferred_replica_store = data.get("replica_store", {})
                self.replica_store.update(transferred_replica_store)
                # For each replica key, re-initiate replication from this node, exept for the keys in data_store.
                for key, value in transferred_replica_store.items():
                    if key not in transferred_data_store:
                        threading.Thread(
                            target=self.async_replicate_insert,
                            args=(key, value, self.replication_factor - 1)
                        ).start()
                
                # Cleanup replicas
                for node_info in ring:
                    node_ip = node_info["ip"]
                    node_port = node_info["port"]
                    cleanup_url = f"http://{node_ip}:{node_port}/cleanup_replicas_all"
                    payload = {
                        "ring": ring,
                        "replication_factor": self.replication_factor
                    }
                    try:
                        requests.post(cleanup_url, json=payload, timeout=2)
                    except Exception as e:
                        print(f"Error triggering cleanup on node {node_ip}:{node_port}: {e}")


                print(f"[{self.ip}:{self.port}] Joined network")
                print(f"[{self.ip}:{self.port}] Updated local data_store with keys: {list(transferred_data_store.keys())}")
                return True
            else:
                return False
        except Exception as e:
            print("Error joining network:", e)
            return False
        
    def cleanup_replicas(self, ring, replication_factor):
        # Remove replica keys from this node's replica_store that are no longer valid
        # according to the new ring ordering.
        keys_to_remove = []
        ring_len = len(ring)
        for key in list(self.replica_store.keys()):
            key_hash = self.compute_hash(key)
            primary_index = None
            # Find the first node whose id is >= key_hash.
            for i, node in enumerate(ring):
                if key_hash <= node["id"]:
                    primary_index = i
                    break
            # If none found, the primary is the first node (wrap-around).
            if primary_index is None:
                primary_index = 0

            # The valid replica holders are the next replication_factor-1 nodes after primary.
            valid_replicas = []
            for j in range(1, replication_factor):
                valid_replicas.append(ring[(primary_index + j) % ring_len]["id"])

            # If this node's id is not among the valid replica holders, delete the key.
            if self.id not in valid_replicas:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.replica_store[key]
        if keys_to_remove:
            print(f"[{self.ip}:{self.port}] Cleanup: removed replicas {keys_to_remove}")
        else:
            print(f"[{self.ip}:{self.port}] Cleanup: no replicas removed")

        
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

    # Method for gracefully departing from the ring.            
    def depart(self):
        # If this is the bootstrap node, it cannot depart.
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

        print(f"[{self.ip}:{self.port}] Departing gracefully from the ring. Still in depart")

        # Notify the bootstrap to remove this node from the ring.
        updated_ring = []
        try:
            remove_url = f"http://{self.bootstrap_ip}:{self.bootstrap_port}/remove_node"
            data = {
                "id": self.id,
                "ip": self.ip,
                "port": self.port
            }
            remove_response = requests.post(remove_url, json=data)
            if remove_response.status_code == 200:
                updated_ring = remove_response.json().get("ring", [])
                print(f"[{self.ip}:{self.port}] Received updated ring: {updated_ring}")
                
                # Trigger cleanup on all nodes in the updated ring 
                for node_info in updated_ring:
                    node_ip = node_info["ip"]
                    node_port = node_info["port"]
                    cleanup_url = f"http://{node_ip}:{node_port}/cleanup_replicas_all"
                    payload = {
                        "ring": updated_ring,
                        "replication_factor": self.replication_factor
                    }
                    try:
                        requests.post(cleanup_url, json=payload, timeout=2)
                    except Exception as e:
                        print(f"Error triggering cleanup on node {node_ip}:{node_port}: {e}")
                
                # And then trigger a repair step to fill in missing replicas
                for node_info in updated_ring:
                    node_ip = node_info["ip"]
                    node_port = node_info["port"]
                    repair_url = f"http://{node_ip}:{node_port}/repair_replicas_all"
                    payload = {
                        "ring": updated_ring,
                        "replication_factor": self.replication_factor
                    }
                    try:
                        requests.post(repair_url, json=payload, timeout=2)
                    except Exception as e:
                        print(f"Error triggering repair on node {node_ip}:{node_port}: {e}")
            else:
                print(f"[{self.ip}:{self.port}] Failed to remove from ring: {remove_response.text}")
        except Exception as e:
            print(f"Error informing bootstrap to remove node: {e}")

        # Clean up local stores.
        self.data_store.clear()
        self.replica_store.clear()
        print(f"[{self.ip}:{self.port}] Departed gracefully from the ring.")
        return True

    def cleanup_replicas(self, ring, replication_factor):
        # For each key in the replica_store, determine its valid replica holders.
        # If this node's id is not among the valid ones, remove the replica.
        keys_to_remove = []
        ring_len = len(ring)
        for key in list(self.replica_store.keys()):
            key_hash = self.compute_hash(key)
            # Determine the primary for the key.
            primary_index = None
            for i, node in enumerate(ring):
                if key_hash <= node["id"]:
                    primary_index = i
                    break
            if primary_index is None:
                primary_index = 0
            # Expected replica holders are the next replication_factor-1 nodes.
            valid_replicas = []
            for j in range(1, replication_factor):
                valid_replicas.append(ring[(primary_index + j) % ring_len]["id"])
            if self.id not in valid_replicas:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self.replica_store[key]
        if keys_to_remove:
            print(f"[{self.ip}:{self.port}] Cleanup: removed replicas {keys_to_remove}")
        else:
            print(f"[{self.ip}:{self.port}] Cleanup: no replicas removed")

    def repair_replicas(self, ring, replication_factor):
        # For each key in this node's data_store, re-initiate replication so that
        # the next replication_factor-1 nodes in the ring get the replica if they don't have it.
        # Find this node's position in the ring.
        primary_index = None
        for i, node in enumerate(ring):
            if node["id"] == self.id:
                primary_index = i
                break
        if primary_index is None:
            return
        # Show ring:
        print(f"[{self.ip}:{self.port}] Repair: Ring: {ring}")

        #self.update_local_pointers(ring)
        for key, value in self.data_store.items():
            # Trigger asynchronous replication chain for each key.
            # This will push the key to the next (replication_factor-1) nodes.
            self.async_replicate_insert(key, value, replication_factor - 1)
        print(f"[{self.ip}:{self.port}] Repair: Re-initiated replication for keys: {list(self.data_store.keys())}")
