"""Node 1: works normally. hello -> heartbeats -> goodbye on Ctrl+C."""
import time
from common import DumbNode, node_args, HELLO, HEARTBEAT, GOODBYE

args = node_args(__doc__)
node = DumbNode("node-1-normal")
node.send(HELLO)
try:
    while True:
        time.sleep(args.interval)
        node.send(HEARTBEAT)
except KeyboardInterrupt:
    node.send(GOODBYE)
