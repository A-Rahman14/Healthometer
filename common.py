"""Shared helpers for the Healthometer POC (standard library only)."""
import argparse
import json
import socket
import time
from datetime import datetime

HOST = "127.0.0.1"
HEALTHOMETER_ADDR = (HOST, 9000)

# Registry of nodes the healthometer knows about (a registered node that has
# never sent anything is "Offline"). For 200 nodes, load this from a file.
NODES = [
    "node-1-normal",
    "node-2-offline",
    "node-3-outdated",
    "node-4-failing",
    "node-5-disabled",
    "node-6-clock-issue",
]

# Message types
HELLO="hello"
HEARTBEAT="heartbeat"
GOODBYE="goodbye"
MESSAGE_TYPES = [HELLO, HEARTBEAT, GOODBYE]

DEFAULT_INTERVAL = 30  # seconds between heartbeats


def pack(**fields):
    return json.dumps(fields).encode("utf-8")


def unpack(data):
    try:
        msg = json.loads(data.decode("utf-8"))
        return msg if isinstance(msg, dict) else None
    except (ValueError, UnicodeDecodeError):
        return None


def fmt(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "-"


def node_args(description):
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                   help="heartbeat interval in seconds (default 30)")
    return p.parse_args()


class DumbNode:
    """A send-only simulated node. It never reads or reacts to responses."""

    def __init__(self, node_id):
        self.node_id = node_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, mtype, timestamp=None):
        ts = time.time() if timestamp is None else timestamp
        self.sock.sendto(pack(type=mtype, node_id=self.node_id, timestamp=ts),
                         HEALTHOMETER_ADDR)
        print(f"[{datetime.now():%H:%M:%S}] {self.node_id}: sent {mtype}", flush=True)
