"""Node 3: outdated data. Heartbeats carry a timestamp 5 intervals in the past."""
import time
from common import DumbNode, node_args, HELLO, HEARTBEAT, GOODBYE

args = node_args(__doc__)
node = DumbNode("node-3-outdated")
node.send(HELLO)
try:
    while True:
        time.sleep(args.interval)
        node.send(HEARTBEAT, timestamp=time.time() - 5 * args.interval)
except KeyboardInterrupt:
    node.send(GOODBYE)
