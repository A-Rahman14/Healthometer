"""Node 6: clock issue. Heartbeat timestamps are in the future (clock ahead)."""
import time
from common import DumbNode, node_args, HELLO, HEARTBEAT, GOODBYE

args = node_args(__doc__)
node = DumbNode("node-6-clock-issue")
node.send(HELLO)
try:
    while True:
        time.sleep(args.interval)
        node.send(HEARTBEAT, timestamp=time.time() + 30)
except KeyboardInterrupt:
    node.send(GOODBYE)
