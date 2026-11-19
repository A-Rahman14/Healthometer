# Healthometer – POC

The healthometer is a small program, which is designed to monitor the MIoT nodes.
It classifies their health, answers every message, requests recovery when needed,
logs everything and keeps a live status summary.

In this PoC there are six simulated "dumb" nodes connected the healthometer.
The nodes only send; they never read or react to the healthometer's responses.

## Requirements

- Python 3.8 or newer. **No extra packages** (standard library only).
- Uses UDP on localhost, port 9000 (healthometer).

## Run it

Quick demo (everything at once, 5 s heartbeats instead of 60 s):

    python run_demo.py --interval 5

Real timing (1 minute heartbeats):

    python run_demo.py

Or run each program in its own terminal (healthometer first;
recommended to use the same `--interval` everywhere):

    python healthometer.py      --interval 5
    python node_normal.py       --interval 5
    python node_offline.py      --interval 5
    python node_outdated.py     --interval 5
    python node_failing.py      --interval 5
    python node_disabled.py     --interval 5
    python node_clock_issue.py  --interval 5

Ctrl+C stops a node cleanly (it sends goodbye -> Offline). Closing/killing its
window sends nothing (could be a power loss), so it will be reported as Not Responding.

## Messages

Node -> healthometer: `hello` (startup), `heartbeat` (+ timestamp), `goodbye` (shutdown).
Healthometer -> node: `ack` (ok) for every message, or `recover`
(please attempt safe recovery; sent for Outdated, Clock Issue, Not Responding). The simulated nodes ignore both.

## Statuses

| Status         | Rule                                                                                                                                              |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Offline        | node has never sent any message, **or** has been intentionally disabled (stopped on purpose; the `last_message` column shows `goodbye`)           |
| Online         | heartbeats arrive and the timestamp is fresh                                                                                                      |
| Outdated       | heartbeat timestamp is older than `--max-lag` (default: 1 interval) -> `recover` sent instead of `ack`                                            |
| Clock Issue    | heartbeat timestamp is later than the healthometer's time (even by 1 ms) -> `recover` sent instead of `ack`                                       |
| Not Responding | nothing received for 2 x interval and no goodbye (crash, power loss, network issue, closed window) -> `recover` sent, repeated every 2 x interval |

## The simulated nodes

| Program               | Behaviour                                                                |
| --------------------- | ------------------------------------------------------------------------ |
| `node_normal.py`      | hello, heartbeats, goodbye on Ctrl+C                                     |
| `node_offline.py`     | never sends anything                                                     |
| `node_outdated.py`    | heartbeats with timestamps 5 intervals in the past                       |
| `node_failing.py`     | 3 heartbeats, then silence (no goodbye)                                  |
| `node_disabled.py`    | 3 heartbeats, then goodbye and exit (-> Offline, last_message = goodbye) |
| `node_clock_issue.py` | heartbeats with timestamps 30 s in the future                            |

## Output files (created next to the scripts)

- `healthometer.log` – every message, status change and recovery request
- `status.md` / `status.csv` – live summary, rewritten every second
  (columns: node, status, last_message, last_message_at, seconds_since, recovery_requests)

## Robustness

The healthometer ignores socket errors (e.g. Windows `ConnectionResetError`
when a node's window is closed) and exceptions while handling a message, so a
misbehaving node can't stop it.

## Scaling to 200 nodes

Nodes are registered in `NODES` in `common.py` (needed to detect Offline).
Load this from a file/DB beyond the POC.
