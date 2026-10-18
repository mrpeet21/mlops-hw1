
import csv
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("results")
OUTPUT_DIR.mkdir(exist_ok=True)

CSV_PATH = OUTPUT_DIR / "hpa-monitor.csv"
EVENTS_PATH = OUTPUT_DIR / "hpa-events.txt"

INTERVAL = 10


def kubectl(*args):
    result = subprocess.run(
        ["kubectl", *args],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    return result.stdout


def collect_metrics():
    hpa = json.loads(
        kubectl("get", "hpa", "cancer-service", "-o", "json")
    )

    status = hpa["status"]
    spec = hpa["spec"]

    cpu_percent = None

    for metric in status.get("currentMetrics", []):
        if metric.get("resource", {}).get("name") == "cpu":
            cpu_percent = metric["resource"]["current"].get(
                "averageUtilization"
            )

    target_cpu = spec["metrics"][0]["resource"]["target"][
        "averageUtilization"
    ]

    try:
        pod_cpu = kubectl(
            "top",
            "pods",
            "-l",
            "app=cancer-service",
            "--no-headers",
        ).strip().replace("\n", "; ")
    except subprocess.CalledProcessError:
        pod_cpu = "metrics unavailable"

    return {
        "timestamp": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "current_replicas": status.get("currentReplicas"),
        "desired_replicas": status.get("desiredReplicas"),
        "cpu_percent": cpu_percent,
        "target_cpu_percent": target_cpu,
        "pod_resources": pod_cpu,
    }


def main():
    columns = [
        "timestamp",
        "current_replicas",
        "desired_replicas",
        "cpu_percent",
        "target_cpu_percent",
        "pod_resources",
    ]

    print("Monitoring HPA every 10 seconds")
    print("Press Ctrl+C to stop\n")

    try:
        with CSV_PATH.open(
            "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()

            while True:
                try:
                    metrics = collect_metrics()
                    writer.writerow(metrics)
                    file.flush()

                    print(
                        f"{metrics['timestamp']} | "
                        f"Replicas: {metrics['current_replicas']} | "
                        f"Desired: {metrics['desired_replicas']} | "
                        f"CPU: {metrics['cpu_percent']}%"
                    )

                except (
                    subprocess.SubprocessError,
                    json.JSONDecodeError,
                    KeyError,
                ) as error:
                    print(f"Monitoring error: {error}")

                time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print("\nMonitoring stopped")

    finally:
        try:
            events = kubectl(
                "get",
                "events",
                "--field-selector",
                "involvedObject.kind=HorizontalPodAutoscaler,"
                "involvedObject.name=cancer-service",
                "--sort-by=.lastTimestamp",
            )
            EVENTS_PATH.write_text(events, encoding="utf-8")
            print(f"Events saved to {EVENTS_PATH}")

        except subprocess.SubprocessError as error:
            print(f"Could not save events: {error}")

    print(f"Metrics saved to {CSV_PATH}")


if __name__ == "__main__":
    main()
