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
  - [Basic API Interactions](#basic-api-interactions)
- [Linux Commands](#linux-commands)
- [Windows Commands](#windows-commands)
- [Docker Compose](#docker-compose)
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

---

## Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)


---

## Docker Setup
### Creating the Network
Create a Docker network for the Chordify application:

```bash
docker network create chord-network
```
### Running the Bootstrap Node
Start the bootstrap node (the first, stable node in the system) with:
```bash
docker run --name bootstrap --network chord-network --env-file .env -p 8000:8000 --rm chordify python bootstrap.py
```
---

### Basic API Interactions
After starting the bootstrap node, you can interact with the API:

Update replication and consistency settings:
```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"replication_factor": 3, "consistency_mode": "eventual"}' \
     http://127.0.0.1:8000/update_settings
```
Insert a song:
```bash
curl -X POST http://127.0.0.1:8001/insert \
     -H "Content-Type: application/json" \
     -d '{"key": "song1", "value": "node8001"}'
```
Query a song:
```bash
curl -X GET "http://127.0.0.1:8001/query?key=song1"
```
---

## Linux Commands
### For users running on Windows, PowerShell commands replace the typical curl syntax:

Insert a song:
```bash
Invoke-WebRequest -Uri "http://127.0.0.1:8001/insert" `
  -Method Post `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{"key": "song1", "value": "Imagine"}'
```
Query a song:

```bash
Invoke-WebRequest -Uri "http://127.0.0.1:8001/query?key=song1" -Method Get
```
Delete a song:

```bash
Invoke-WebRequest -Uri "http://127.0.0.1:8001/delete" `
  -Method Post `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{"key": "song1"}'
```
Display network overlay:

```bash
(Invoke-WebRequest -Uri "http://127.0.0.1:8001/overlay" -Method GET).Content
```
Depart from the network:

```bash
Invoke-WebRequest -Uri http://localhost:8001/depart -Method POST
```
---
## Windows Commands
### For users running on Windows, PowerShell commands replace the typical curl syntax:

Insert a song:
```bash
Invoke-WebRequest -Uri "http://127.0.0.1:8001/insert" `
  -Method Post `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{"key": "song1", "value": "Imagine"}'
```
Query a song:

```bash
Invoke-WebRequest -Uri "http://127.0.0.1:8001/query?key=song1" -Method Get
```
Delete a song:

```bash
Invoke-WebRequest -Uri "http://127.0.0.1:8001/delete" `
  -Method Post `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{"key": "song1"}'
```
Display network overlay:

```bash
(Invoke-WebRequest -Uri "http://127.0.0.1:8001/overlay" -Method GET).Content
```
Depart from the network:

```bash
Invoke-WebRequest -Uri http://localhost:8001/depart -Method POST
```
---

## Docker Compose
### To build and run the entire system using Docker Compose, use the following commands:
```bash
sudo docker-compose build
sudo docker-compose up
```
---
## Adding New Nodes
### You can add new nodes to the network using the following commands (example for node5 and node6):

adding Node5 :

```bash
sudo docker run -d \
    --network chordify_default \
    --name node5 \
    -v $(pwd):/app \
    -e IP=node5 \
    -e PORT=8005 \
    -p 8005:8005 \
    chordify \
    python app.py --ip node5 --port 8005 --bootstrap_ip bootstrap --bootstrap_port 8000
```
Adding Node6 :
```bash
sudo docker run -d \
    --network chordify_default \
    --name node6 \
    -v $(pwd):/app \
    -e IP=node6 \
    -e PORT=8006 \
    -p 8006:8006 \
    chordify \
    python app.py --ip node6 --port 8006 --bootstrap_ip bootstrap --bootstrap_port 8000
```
---
## Network Operations
### Get network overlay:

```bash
curl -X GET http://127.0.0.1:8001/overlay
Depart a node (example on port 8002):
```
### Depart a node (example on port 8002):
```bash
curl -X POST http://localhost:8002/depart
```
---

## DHT Operations
### Insert / Query / Delete
Insert (from node3):

```bash
curl -X POST http://node3:8000/insert \
     -H "Content-Type: application/json" \
     -d '{"key": "Imagine"}'
```
Delete (song3 from node1):
```bash
curl -X POST http://127.0.0.1:8001/delete \
     -H "Content-Type: application/json" \
     -d '{"key": "song3"}'
```
---

## AWS Deployment
## The following commands outline the steps for deploying Chordify on AWS VMs:

Reset the Git repository:

```bash
git restore *
Stop and remove all containers:
```
Stop and remove all containers:

```bash

sudo docker rm -f $(sudo docker ps -aq)
Build the Docker image:
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

Run experiments:
Deploy two nodes on other VMs:
```bash
python3 request_expirement.py --bootstrap_ip 10.0.62.44 --bootstrap_port 8000 --num_nodes 4
```

Change replication and consistency settings (which also clears all songs):
```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"replication_factor": 1, "consistency_mode": "linearizability"}' \
     http://10.0.62.44:8000/update_settings
```

Node information examples (IP:port and node identifiers):
```bash
44:8000      -> Node 0
183:8002     -> Node ID: 24143611642021087769965016016911796183215422724
48:8001      -> Node ID: 75142041091136173815320167490110446356621531987
4:8001       -> Node ID: 100327599628895595809874772797002322028919969014
44:8001      -> Node ID: 295932134150687556341207193662481870356174536331
217:8001     -> Node ID: 411874805086580080154720257350036684338272740759
48:8002      -> Node ID: 547855836760873760974161719315521171288480286053
183:8001     -> Node ID: 739793560834826224520256699940780490425450258197
4:8002       -> Node ID: 1376187645279844781901574523592213044469256684617
217:8002     -> Node ID: 1395659438043788344394894604843344294049593540490
```
---
## Additional Commands
Get network overlay:

```bash

curl -X GET http://10.0.62.183:8001/overlay
```

Get node information:

```bash

curl -X GET http://10.0.62.183:8001/nodeinfo
```

Query all keys in the DHT:
```bash
curl -X GET "http://10.0.62.183:8001/query?key=*"
```
---

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

