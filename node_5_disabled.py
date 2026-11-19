"""Node 5: intentionally shut down (shows as Offline with last_message = goodbye). 3 heartbeats, then goodbye and exit."""
import time
from common import DumbNode, node_args, HELLO, HEARTBEAT, GOODBYE

DISABLE_AFTER = 3

args = node_args(__doc__)
node = DumbNode("node-5-disabled")
node.send(HELLO)
try:
    for _ in range(DISABLE_AFTER):
        time.sleep(args.interval)
        node.send(HEARTBEAT)
    time.sleep(args.interval)
except KeyboardInterrupt:
    pass
node.send(GOODBYE)
