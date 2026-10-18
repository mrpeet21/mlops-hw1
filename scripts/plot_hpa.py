
import csv
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

CSV_PATH = Path("results/hpa-monitor.csv")
OUTPUT_PATH = Path("results/hpa-scaling.png")

with CSV_PATH.open(encoding="utf-8", newline="") as file:
    rows = list(csv.DictReader(file))

timestamps = [
    datetime.fromisoformat(row["timestamp"])
    for row in rows
]

replicas = [
    int(row["current_replicas"])
    for row in rows
]

cpu = [
    float(row["cpu_percent"])
    if row["cpu_percent"]
    else float("nan")
    for row in rows
]

# Начало и завершение реального нагрузочного теста
load_start = datetime.fromisoformat(
    "2026-10-18T20:07:04+03:00"
)
load_end = datetime.fromisoformat(
    "2026-10-18T20:10:02+03:00"
)

fig, ax1 = plt.subplots(figsize=(13, 6))

# Левая ось — число реплик
line1 = ax1.step(
    timestamps,
    replicas,
    where="post",
    color="tab:blue",
    linewidth=2.5,
    label="Replicas",
)

ax1.set_ylabel("Number of replicas", color="tab:blue")
ax1.set_ylim(1.5, 6.5)
ax1.set_yticks(range(2, 7))

# Правая ось — загрузка CPU
ax2 = ax1.twinx()

line2 = ax2.scatter(
    timestamps,
    cpu,
    color="tab:orange",
    s=14,
    label="CPU utilization",
)

ax2.axhline(
    60,
    color="tab:red",
    linestyle="--",
    linewidth=1.5,
    label="CPU target: 60%",
)

ax2.set_ylabel("CPU utilization (% of requests)")
ax2.set_ylim(bottom=0)

# Отмечаем интервал работы Locust
ax1.axvspan(
    load_start,
    load_end,
    color="gray",
    alpha=0.15,
    label="Locust load test",
)

ax1.set_title("Kubernetes HPA: CPU Utilization and Replica Scaling")
ax1.set_xlabel("Time")
ax1.xaxis.set_major_formatter(
    mdates.DateFormatter("%H:%M", tz=timestamps[0].tzinfo)
)
ax1.grid(axis="x", alpha=0.3)

# Общая легенда
handles1, labels1 = ax1.get_legend_handles_labels()
handles2, labels2 = ax2.get_legend_handles_labels()

ax1.legend(
    handles1 + handles2,
    labels1 + labels2,
    loc="upper right",
)

fig.autofmt_xdate()
fig.tight_layout()

fig.savefig(OUTPUT_PATH, dpi=180)
print(f"Saved: {OUTPUT_PATH}")

plt.show()
