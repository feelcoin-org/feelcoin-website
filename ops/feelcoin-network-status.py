#!/usr/bin/env python3

import json
import urllib.request
from datetime import datetime, timezone

RPC = "http://127.0.0.1:35781"
NODE2_IP = "129.121.148.149"
OUT = "/var/www/feelcoin.online/network-status.json"


def get_json(url, data=None):
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(
        url,
        data=data.encode() if data else None,
        headers=headers
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


# Node1
info = get_json(RPC + "/get_info")

# P2P connections seen by Node1
payload = json.dumps({
    "jsonrpc": "2.0",
    "id": "0",
    "method": "get_connections"
})

connections = get_json(RPC + "/json_rpc", payload)
peers = connections.get("result", {}).get("connections", [])

node2 = None

for peer in peers:
    if peer.get("host") == NODE2_IP:
        node2 = peer
        break

data = {
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "network": {
        "name": "Feelcoin",
        "ticker": "FEEL",
        "target_seconds": info.get("target", 120),
        "height": info.get("height"),
        "difficulty": info.get("difficulty"),
        "synchronized": info.get("synchronized")
    },
    "nodes": {
        "node1": {
            "name": "Node 1",
            "host": "node1.feelcoin.org",
            "p2p_port": 35780,
            "online": True,
            "height": info.get("height"),
            "incoming": info.get("incoming_connections_count"),
            "outgoing": info.get("outgoing_connections_count"),
            "synchronized": info.get("synchronized")
        },
        "node2": {
            "name": "Node 2",
            "host": "node2.feelcoin.org",
            "p2p_port": 35780,
            "online": node2 is not None,
            "height": node2.get("height") if node2 else None,
            "state": node2.get("state") if node2 else "offline"
        }
    }
}

tmp = OUT + ".tmp"

with open(tmp, "w") as f:
    json.dump(data, f, indent=2)

import os
os.replace(tmp, OUT)
