# Chordify: A Peer-to-Peer Song Sharing Application

Chordify is a distributed file sharing application built on a Chord Distributed Hash Table (DHT). This project enables users to share songs by inserting, querying, and deleting song entries. Each song is identified by its title (the key), and the value is a string representing the node where the song is available. The application supports node joins, graceful departures, data replication with a configurable replication factor, and two consistency models: **linearizability** and **eventual consistency**.

> **Note:** This project is developed as part of the Distributed Systems course (2024-2025) at the National Metsovio Polytechnic. It is based on the Chord DHT design introduced in the seminal paper by Stoica et al. (2001).

---

## Table of Contents

- [Overview](#overview)
- [Project Features](#project-features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Running with Docker](#running-with-docker)
  - [Docker Compose](#docker-compose)
  - [Adding New Nodes](#adding-new-nodes)
  - [Queries and CRUD Operations](#queries-and-crud-operations)
- [AWS Deployment](#aws-deployment)
- [Additional Commands](#additional-commands)
- [Assignment Summary](#assignment-summary)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## Overview

Chordify is designed as a P2P song sharing system where:

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



