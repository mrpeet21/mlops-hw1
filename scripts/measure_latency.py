import statistics

import httpx


URL = "http://localhost:8000/v1/predict"

PAYLOAD = {
    "mean_radius": 14.0,
    "mean_texture": 20.0,
    "mean_perimeter": 90.0,
    "mean_area": 600.0,
    "mean_smoothness": 0.1,
    "mean_compactness": 0.12,
}


latencies = []

for i in range(10):
    response = httpx.post(
        URL,
        json=PAYLOAD,
        timeout=10,
    )

    response.raise_for_status()

    latency = response.json()["latency_ms"]

    latencies.append(latency)

    print(
        f"{i + 1:2d}: "
        f"{latency:.3f} ms"
    )


print()
print(
    f"median: "
    f"{statistics.median(latencies):.3f} ms"
)

print(
    f"max: "
    f"{max(latencies):.3f} ms"
)