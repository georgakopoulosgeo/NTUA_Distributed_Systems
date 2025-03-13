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

Create a Docker network for the Chordify application:

```bash
docker network create chord-network
```
### Running the Bootstrap Node
Start the bootstrap node (the first, stable node in the system) with:
```bash
docker run --name bootstrap --network chord-network --env-file .env -p 8000:8000 --rm chordify python bootstrap.py
```
###Basic API Interactions
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
###Linux Commands
For users running on Windows, PowerShell commands replace the typical curl syntax:

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
###Windows Commands
For users running on Windows, PowerShell commands replace the typical curl syntax:

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

- **ID Assignment:** Each node gets a unique ID derived from the SHA1 hash of its `ip_address:port`.
- **Core Operations:** Supports `insert`, `query`, and `delete` of key-value pairs. Duplicate inserts update (concatenate) the existing value.
- **Wildcard Query:** Using the special key `*` returns all key-value pairs from across the DHT.
- **Node Management:** Implements node join and graceful departure, ensuring that routing pointers (successor/predecessor) are updated appropriately.
- **Replication:** Each key-value pair is replicated on _k_ nodes (configurable replication factor).
- **Consistency Models:** Offers:
  - **Linearizability:** Strong consistency achieved via quorum or chain replication.
  - **Eventual Consistency:** Updates propagate lazily, possibly returning stale values in read operations.

---

## Project Features

- **Chord DHT Architecture:** Organizes nodes in a logical ring with consistent hashing.
- **Peer-to-Peer Communication:** Each node runs both server and client processes and communicates via sockets.
- **Dynamic Node Operations:** Handles node joins and departures with minimal disruption.
- **Configurable Consistency:** Switch between linearizability and eventual consistency modes.
- **CLI Client:** Provides a simple command-line interface to execute operations like insert, delete, query, depart, overlay, and help.

---

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)
- Git
- (Optional) AWS environment for deployment

### Running with Docker

#### 1. Create a Docker Network and Start the Bootstrap Node

```bash
docker network create chord-network

docker run --name bootstrap --network chord-network --env-file .env -p 8000:8000 --rm chordify python bootstrap.py
```
#### 2. Inserting, Updating, and Querying Songs (Linux/macOS)
```bash
curl -X POST http://127.0.0.1:8001/insert \
  -H "Content-Type: application/json" \
  -d '{"key": "song1", "value": "node8001"}'

curl -X POST -H "Content-Type: application/json" \
  -d '{"replication_factor": 3, "consistency_mode": "eventual"}' \
  http://127.0.0.1:8000/update_settings

curl -X GET "http://127.0.0.1:8001/query?key=song1"
```

#### 3. Inserting, Updating, and Querying Songs (Linux/macOS)
```bash
Invoke-WebRequest -Uri "http://127.0.0.1:8001/insert" `
  -Method Post `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{"key": "song1", "value": "Imagine"}'

Invoke-WebRequest -Uri "http://127.0.0.1:8001/query?key=song1" -Method Get  

curl -X GET "http://127.0.0.1:8001/query?key=song1"
```
