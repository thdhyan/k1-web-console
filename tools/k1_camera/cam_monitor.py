"""Run ON a K1 (humble). Logs per-window Hz of the head camera topics to detect dropout.

  source /opt/ros/humble/setup.bash; python3 cam_monitor.py [--minutes 30] [--window 10]
One line per window: wall time, uptime, Hz per topic, and DROP marker when any stereo/depth topic < 5 Hz.
"""
import argparse, time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import Image

TOPICS = ["/boostercamera/head/rgb", "/boostercamera/head/right/rgb", "/boostercamera/head/depth",
          "/boostercamera/head/raw/rgb", "/boostercamera/head/raw/right/rgb"]
ap = argparse.ArgumentParser()
ap.add_argument("--minutes", type=float, default=30)
ap.add_argument("--window", type=float, default=10)
a = ap.parse_args()

rclpy.init()
n = Node("cam_monitor")
qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)
cnt = {t: 0 for t in TOPICS}
for t in TOPICS:
    n.create_subscription(Image, t, lambda m, t=t: cnt.__setitem__(t, cnt[t] + 1), qos)
up = lambda: float(open("/proc/uptime").read().split()[0]) / 60
end = time.time() + a.minutes * 60
print("time uptime_min " + " ".join(t.split("/head/")[1] for t in TOPICS), flush=True)
while time.time() < end:
    for t in TOPICS: cnt[t] = 0
    w0 = time.time()
    while time.time() - w0 < a.window:
        rclpy.spin_once(n, timeout_sec=0.1)
    hz = [cnt[t] / (time.time() - w0) for t in TOPICS]
    drop = "  DROP" if min(hz[0], hz[2]) < 5 else ""
    print(f"{time.strftime('%H:%M:%S')} {up():6.1f} " + " ".join(f"{h:5.1f}" for h in hz) + drop, flush=True)
