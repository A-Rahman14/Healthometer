"""Starts the healthometer and all six nodes, each in its own process.
Usage: python run_demo.py [--interval 60]   (Ctrl+C stops everything)"""
import subprocess
import sys
import time
from common import node_args

args = node_args(__doc__)
interval = str(args.interval)
programs = [["healthometer.py"], ["node_1_normal.py"], ["node_2_offline.py"],
         ["node_3_outdated.py"], ["node_4_failing.py"], ["node_5_disabled.py"],
         ["node_6_clock_issue.py"]]
processes = []
try:
    for i, p in enumerate(programs):
        processes.append(subprocess.Popen([sys.executable] + p + ["--interval", interval]))
        time.sleep(0.5 if i == 0 else 0.1)
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    time.sleep(2)
    for p in processes:
        if p.poll() is None:
            p.terminate()
