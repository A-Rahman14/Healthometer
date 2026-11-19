"""Node 4: service failure. Sends 3 heartbeats, then goes silent (no goodbye)."""
import time
from common import DumbNode, node_args, HELLO, HEARTBEAT

CRASH_AFTER = 3

args = node_args(__doc__)
node = DumbNode("node-4-failing")
node.send(HELLO)
try:
    for _ in range(CRASH_AFTER):
        time.sleep(args.interval)
        node.send(HEARTBEAT)
    print("HINT: now node-4-failing crashed, so no more messages are sent.")
except KeyboardInterrupt:
    pass
