# Chordify

Chordify is a peer-to-peer (P2P) music sharing application built on top of the Chord Distributed Hash Table (DHT) protocol. In this project, nodes share song metadata (with the song title as the key and a string representing the node's address as the value). The system supports dynamic node joining and graceful departures, data replication across multiple nodes, and two consistency modes—linearizability and eventual consistency.

This project was developed as part of the Distributed Systems course at the National Technical University of Athens (NTUA) for the 2024-2025 academic year.

---

## Table of Contents

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Docker Setup](#docker-setup)
  - [Creating the Network](#creating-the-network)
  - [Running the Bootstrap Node](#running-the-bootstrap-node)
  - [Basc API Interactions](#basic-api-interactions)
- [Linux Commands](#linux-commands)
- [Windows Commands](#windows-commands)
- [Docker Comipose](#docker-compose)
- [Adding New Nodes](#adding-new-nodes)
- [Network Operations](#network-operations)
- [DHT Operations](#dht-operations)
- [AWS Deployment](#aws-deployment)
- [Experiments](#experiments)
- [Conclusion](#conclusion)

---

## Introduction

Chordify implements a simplified version of the Chord DHT protocol. Each node is responsible for a range of keys derived from applying the SHA1 hash on the combination `ip_address:port`. The basic operations include:

- **insert(key, value):** Adds a new song or updates an existing one (by concatenating values).
- **query(key):** Retrieves the value associated with a key; using `"*"` returns all key-value pairs across the DHT.
- **delete(key):** Removes the key-value pair from the network.
- **depart:** Allows a node to gracefully exit, updating its neighbors.
- **overlay:** Displays the current network topology.

The system supports data replication (with a configurable replication factor) and offers both linearizability (using quorum or chain replication) and eventual consistency options.


## Node Structure
- Every node runs as a standalone server and client using Flask for HTTP-based communication. Nodes maintain pointers to their immediate neighbors in the ring.
- Bootstrap Node: Acts as the gateway for new nodes to join the network. It provides new nodes with the initial routing information.
- Replication: Data is replicated across multiple nodes for fault tolerance. The replication factor and consistency mode (linearizability or eventual consistency) are defined during initialization.
- Communication: Nodes communicate asynchronously via HTTP requests, using a "fire, forget and callback" mechanism to enhance performance.

## Consistency Models
Chordify offers two consistency modes to handle data replication:

### Linearizability
- Definition: Guarantees that all replicas of a key are updated synchronously so that every read returns the most recent value.
- Mechanism: Implemented via chain replication. Write operations are forwarded along a chain of nodes and are confirmed only when the tail node (which holds the most up-to-date data) completes the update.
- Operation Impact:
  - Insert/Delete: Slower response times due to the need for confirmation from all replicas.
  - Query: Always returns the freshest value by reading from the tail node.

### Eventual Consistency
- Definition: Allows replicas to update asynchronously. Although not immediately consistent, the system will converge to a consistent state over time.
- Mechanism: Writes are applied at the primary node, which immediately responds to the client while propagating the update to the replicas in the background.
- Operation Impact:
  - Insert/Delete: Faster responses, but there is a risk that queries might return stale data if updates haven’t fully propagated.
  - Query: Can be served by any node, offering speed at the expense of potential temporary inconsistencies.

For further details on these models and the performance implications of each operation under different settings, please refer to the detailed report provided with this project.

## Prerequisites

- Docker. 
  - Debian Linux:

    ```bash
    sudo snap install docker
    ```
  - Windows: Follow the instructions at [Docker_Windows](https://docs.docker.com/desktop/setup/install/windows-install/)

- Python 3.8 or higher
- Required Python modules listed in `requirements.txt`:

    ```bash
    pip install -r requirements.txt
    ```

    Alternatively, you can install the modules individually:

    ```bash
    pip install Flask flask-cors requests python-dotenv
    ```



## LocalHost Deployment - Docker (Debian Linux)
### Step 1: Creating the Network
In **/chordify**, create a Docker network for the Chordify application and the chordify image:

```bash
sudo docker network create chord-network
```
```bash
sudo docker build -t chordify .
```

### Step 2: Create 5 containers with Docker-Compose
To build and run the entire system using Docker Compose, use the following commands:
```bash
sudo docker-compose build
sudo docker-compose up
```
These commands will create all containers specified in docker-compose.yml

### Step 3: Create more nodes
To create an extra node for this network, use the following command:

```bash
sudo docker run -d \
  --network chordify_default \
  --name <node_name> \
  -v $(pwd):/app \
  -e IP=<node_name> \
  -e PORT=<node_port> \
  -p <node_port>:<node_port> \
  chordify \
  python app.py --ip <node_name> --port <node_port> --bootstrap_ip bootstrap --bootstrap_port 8000
```

Replace `<node_name>` with the desired node name and `<node_port>` with the desired port number.




## AWS Deployment

To deploy the Chordify application on AWS, follow these three steps:

### Step 1: Reset the Git repository
Ensure you have the latest version of the repository:

```bash
git restore *
git pull
```

### Step 2: Stop and remove all containers, then build the Docker image
Make sure there are no previous containers running and build the Docker image:

```bash
sudo docker rm -f $(sudo docker ps -aq)
sudo docker build -t chord-app .
```

### Step 3: Run the necessary deployment scripts
Deploy the bootstrap node and additional nodes on the VMs:

```bash
cd chordify/scripts/
sudo chmod +x deploy_bootstrap.sh deploy_node.sh
```
For the first VM:
```bash
sudo ./deploy_bootstrap.sh
```
For the other VMs:
```bash
sudo ./deploy_node.sh
```
## Client and Frontend Usage
After deployment, you can interact with the Chordify network in two ways:

- Client CLI:
Start the client interface for the node of your choice with:
  ```bash
  python3 client.py --node <ip>:<port>
  ```

  This CLI allows you to execute operations such as insert, query, delete, depart, and overlay.

- Frontend Interface:
When running on localhost, you can enable the web-based frontend to execute requests via a browser. The frontend offers similar functionalities as the CLI but in a more user-friendly visual format.
To access the frontend interface, open your browser and navigate to:

  ```plaintext
  http://127.0.0.1:5500/chordify/index.html
  ```

  This will load the web-based frontend where you can interact with the Chordify network.
![image](https://github.com/user-attachments/assets/a6c46621-dbdf-469f-a4bb-91527d1bd4ba)


## Experiments

### Experiment 1: Write Throughput
This experiment measures the system’s performance when inserting data. We concurrently insert keys from 10 different input files using various replication factors (k=1, k=3, and k=5) and under both linearizability and eventual consistency modes. The primary metrics are the write throughput (operations per second) and the insert duration (time taken to complete all insert operations).

### Experiment 2: Read Throughput
In this experiment, we evaluate the system’s read performance. By concurrently querying keys from 10 different query files, we measure the read throughput (operations per second) and the query duration (time taken to complete all queries). This experiment helps us understand how different replication factors and consistency models affect the overall speed of data retrieval.

### Experiment 3: Fresh or Stale Reads
This experiment interleaves insert and query operations using a dedicated set of request files. For each query, the system determines whether the returned data is fresh (up-to-date) or stale (not fully updated). The key metric here is the ratio of fresh to stale reads, which reveals the impact of the chosen consistency model on data correctness and timeliness.

### Running the Experiments
- Local Setup:
  Navigate to the **chordify/experiments/** directory and run:
  ```bash
  python3 request_experiment.py --num_nodes n --local
  ```

- Deployment on VMs:
  Run the following cmmand, replacing <ip> and <port> with the appropriate bootstrap node values:

  ```bash
  python3 request_experiment.py --bootstrap_ip <ip> --bootstrap_port <port> --num_nodes n
  ```

The results of the experiments on AWS VMs, are saved in the **schordify/experiments/results/** folder.

####For a detailed description of the experimental setups, an in-depth explanation of the results, and the final conclusions, please refer to the report.pdf.

