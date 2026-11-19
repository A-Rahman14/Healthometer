"""Healthometer: receives node messages, classifies node health, answers every
message, requests safe recovery, logs events and writes a live summary."""
import argparse
import csv
import logging
import os
import socket
import threading
import time

from common import HEALTHOMETER_ADDR, NODES, MESSAGE_TYPES, HELLO, HEARTBEAT, GOODBYE, DEFAULT_INTERVAL, pack, unpack, fmt

# Node statuses
OFFLINE = "Offline"                 # never sent anything, or last message was goodbye
ONLINE = "Online"                   # heartbeats arriving with a fresh timestamp
OUTDATED = "Outdated"               # heartbeat timestamp too old
CLOCK_ISSUE = "Clock Issue"         # heartbeat timestamp is in the future
NOT_RESPONDING = "Not Responding"   # went silent without goodbye


class NodeState:
    def __init__(self):
        self.status = OFFLINE       # node status, starts as offline
        self.addr = None            # address of the node to reply to
        self.last_recv = None       # arrival time of last message
        self.last_type = None       # hello / heartbeat / goodbye
        self.lag = 0.0              # arrival time - heartbeat timestamp
        self.last_recover = None    # time of last recovery request sent to this node
        self.recover_count = 0      # number of recovery requests sent to this node since last hello


class Healthometer:
    def __init__(self, interval, max_lag, out_dir):
        self.interval = interval
        self.max_lag = max_lag
        self.silence_limit = 2 * interval
        self.states = {n: NodeState() for n in NODES}
        self.lock = threading.Lock()
        self.csv_path = os.path.join(out_dir, "status.csv")
        self.md_path = os.path.join(out_dir, "status.md")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Windows: don't raise ConnectionResetError when a node's socket is gone
        if hasattr(socket, "SIO_UDP_CONNRESET"):
            self.sock.ioctl(socket.SIO_UDP_CONNRESET, False)
        self.sock.bind(HEALTHOMETER_ADDR)
        self.sock.settimeout(0.5)
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
            handlers=[logging.FileHandler(os.path.join(out_dir, "healthometer.log"),
                                          encoding="utf-8"),
                      logging.StreamHandler()])
        self.log = logging.getLogger("healthometer")

    # ---- classification -------------------------------------------------
    def evaluate(self, state, time_now):
        if state.last_type is None or state.last_type == GOODBYE:
            return OFFLINE
        if time_now - state.last_recv > self.silence_limit:
            return NOT_RESPONDING
        if state.last_type == HEARTBEAT:
            if state.lag < 0:
                return CLOCK_ISSUE
            if state.lag > self.max_lag:
                return OUTDATED
        return ONLINE

    def set_status(self, node_id, state, new, detail=""):
        if new != state.status:
            lvl = logging.INFO if new in (ONLINE, OFFLINE) else logging.WARNING
            self.log.log(lvl, "%s: %s -> %s %s", node_id, state.status, new, detail)
            state.status = new

    def reply(self, addr, **fields):
        try:
            self.sock.sendto(pack(timestamp=time.time(), **fields), addr)
        except OSError as e:  # node gone: not our problem, never crash
            self.log.debug("reply to %s failed: %s", addr, e)

    def request_recovery(self, node_id, state, reason):
        state.last_recover = time.time()
        state.recover_count += 1
        self.log.warning("%s: sending recovery request #%d (%s)",
                         node_id, state.recover_count, reason)
        self.reply(state.addr, type="recover", reason=reason)

    # ---- receiving ------------------------------------------------------
    def handle(self, data, addr):
        msg = unpack(data)
        if not msg:
            return
        node_id, msg_type = msg.get("node_id"), msg.get("type")
        if node_id not in self.states or msg_type not in MESSAGE_TYPES:
            self.log.warning("ignoring message from unknown sender/type: %s", msg)
            return
        time_now = time.time()
        with self.lock:
            state = self.states[node_id]
            state.addr, state.last_recv, state.last_type = addr, time_now, msg_type
            if msg_type == HEARTBEAT:
                try:
                    state.lag = time_now - float(msg.get("timestamp"))
                except (TypeError, ValueError):
                    self.log.warning("%s: heartbeat without valid timestamp", node_id)
                    state.lag = float("inf")
            else:
                state.lag = 0.0
            self.log.info("%s: received %s (timestamp lag %.3fs)", node_id, msg_type, state.lag)

            if msg_type == HELLO:
                state.last_recover, state.recover_count = None, 0
                self.set_status(node_id, state, ONLINE, "(startup)")
                self.reply(addr, type="ack", **{"for": msg_type})
            elif msg_type == GOODBYE:
                self.set_status(node_id, state, OFFLINE, "(shutdown)")
                self.reply(addr, type="ack", **{"for": msg_type})
            else:
                new = self.evaluate(state, time_now)
                self.set_status(node_id, state, new, f"(lag {state.lag:.3f}s)")
                if new in (OUTDATED, CLOCK_ISSUE):
                    self.request_recovery(
                        node_id, state, OUTDATED if new == OUTDATED else CLOCK_ISSUE)
                else:
                    if new == ONLINE:
                        state.last_recover, state.recover_count = None, 0
                    self.reply(addr, type="ack", **{"for": msg_type})
            self.write_summary()

    # ---- periodic check -------------------------------------------------
    def tick(self):
        time_now = time.time()
        with self.lock:
            for node_id, state in self.states.items():
                new = self.evaluate(state, time_now)
                self.set_status(node_id, state, new,
                                f"(silent for {time_now - (state.last_recv or time_now):.0f}s)")
                if new == NOT_RESPONDING and state.addr and (
                        state.last_recover is None
                        or time_now - state.last_recover >= self.silence_limit):
                    self.request_recovery(node_id, state, NOT_RESPONDING)
            self.write_summary()

    # ---- summary files --------------------------------------------------
    def write_summary(self):
        time_now = time.time()
        header = ["node", "status", "last_message", "last_message_at",
                  "seconds_since", "recovery_requests"]
        rows = []
        for node_id, state in self.states.items():
            age = f"{time_now - state.last_recv:.0f}" if state.last_recv else "-"
            rows.append([node_id, state.status, state.last_type or "-", fmt(state.last_recv),
                         age, state.recover_count])
        self._atomic(self.csv_path, lambda f: csv.writer(f).writerows([header] + rows))

        def md(f):
            f.write(f"# Healthometer live status\n\nUpdated: {fmt(time_now)} | "
                    f"heartbeat interval: {self.interval:g}s | "
                    f"not responding after: {self.silence_limit:g}s\n\n")
            f.write("| " + " | ".join(header) + " |\n")
            f.write("|" + "---|" * len(header) + "\n")
            for r in rows:
                f.write("| " + " | ".join(str(c) for c in r) + " |\n")
        self._atomic(self.md_path, md)

    @staticmethod
    def _atomic(path, writer):
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", newline="", encoding="utf-8") as f:
                writer(f)
            os.replace(tmp, path)
        except OSError:
            pass  # file locked by an editor/viewer; next tick will retry

    # ---- main loop ------------------------------------------------------
    def run(self):
        self.log.info("healthometer started (interval %gs, max lag %gs, silence limit %gs)",
                      self.interval, self.max_lag, self.silence_limit)
        threading.Thread(target=self._ticker, daemon=True).start()
        self.write_summary()
        try:
            while True:
                try:
                    data, addr = self.sock.recvfrom(4096)
                except socket.timeout:
                    continue
                except ConnectionResetError:
                    continue  # Windows: a node's socket vanished (window closed)
                except OSError as e:
                    self.log.warning("socket error ignored: %s", e)
                    time.sleep(0.1)
                    continue
                try:
                    self.handle(data, addr)
                except Exception:
                    self.log.exception("error while handling a message (continuing)")
        except KeyboardInterrupt:
            self.log.info("healthometer stopped")

    def _ticker(self):
        while True:
            time.sleep(1)
            try:
                self.tick()
            except Exception:
                self.log.exception("error in periodic check (continuing)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                    help="expected heartbeat interval in seconds (default 60)")
    ap.add_argument("--max-lag", type=float, default=None,
                    help="max age of a heartbeat timestamp at arrival before it counts "
                         "as outdated (default: one interval)")
    a = ap.parse_args()
    Healthometer(a.interval, a.max_lag or a.interval,
                 os.path.dirname(os.path.abspath(__file__))).run()
