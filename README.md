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
- Communication: Nodes communicate asynchronously via HTTP, using a "fire, forget and callback" mechanism to enhance performance.

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

- [Docker](https://www.docker.com/get-started). 
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


--- 
## LocalHost Deployment - Docker (Debian Linux)
### Creating the Network
In /chordify, create a Docker network for the Chordify application and the chordify image:

```bash
sudo docker network create chord-network
```
```bash
sudo docker build -t chordify .
```

### Create containers with Docker-Compose
To build and run the entire system using Docker Compose, use the following commands:
```bash
sudo docker-compose build
sudo docker-compose up
```
These commands will create all containers specified in docker-compose.yml


---

## AWS Deployment
### The following commands outline the steps for deploying Chordify on AWS VMs:

Reset the Git repository:

```bash
git restore *
```
Stop and remove all containers:

```bash

sudo docker rm -f $(sudo docker ps -aq)
```
Build the Docker image:
```bash

sudo docker build -t chord-app .
```

Deploy the bootstrap node and one additional node on VM1:

```bash
git pull
cd chordify/scritps/
sudo chmod +x deploy_bootstrap.sh
sudo ./deploy_bootstrap.sh
```

Deploy two nodes on other VMs:
```bash
git pull
cd chordify/scritps/
sudo chmod +x deploy_node.sh
sudo ./deploy_node.sh
```

## Client and Frontend Usage
After deployment, you can interact with the Chordify network in two ways:

- Client CLI:
Start the client interface with:
  ```bash
  python3 client.py
  ```

  You will be prompted to enter the IP and port of the node to connect to. This CLI allows you to execute operations such as insert, query, delete, depart, and overlay.

- Frontend Interface:
When running on localhost, you can enable the web-based frontend to execute requests via a browser. The frontend offers similar functionalities as the CLI but in a more user-friendly visual format.

## Experiments 
For performance evaluation, the following experiments are conducted:

Write Throughput:
Insert all keys from the 10 different insert_n.txt files concurrently (using various replication factors: k=1, k=3, k=5) and under both linearizability and eventual consistency modes. The experiment measures how throughput changes with increasing replication factors.

Read Throughput:
Query all keys from the 10 different query_n.txt files concurrently, measuring the read throughput under each setup and comparing the effect of different replication factors.

Mixed Workload Testing:
Run a set of mixed requests from the requests_n.txt files and record query responses under both consistency models. The goal is to determine which consistency mode delivers fresher values.

Results and analysis of these experiments should be documented in a separate report (PDF) along with the source code submission.

---
## Conclusion

Chordify provides a robust implementation of a Chord-based DHT for a music sharing application. With support for replication and configurable consistency models, it serves as a practical implementation of key concepts in distributed systems such as node management, data distribution, and fault tolerance. This project also lays the groundwork for further enhancements such as improved routing (e.g., implementing finger tables) and dynamic scaling.

