#!/usr/bin/env python3
"""Monitor job progression and metrics collection"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"
JOB_IDS = {
    "tcn": "741ddca8",
    "cnn": "654bfaee",
    "lstm": "f5e9c6ef",
    "bigru_attention": "c1619cb7"
}

def monitor_jobs(duration_seconds=60, interval=5):
    """Monitor jobs for specified duration"""
    start_time = time.time()

    print("=" * 70)
    print("  JOB MONITORING AND METRICS COLLECTION")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"Monitoring duration: {duration_seconds}s (checks every {interval}s)")
    print(f"Job IDs: {JOB_IDS}\n")

    iteration = 0
    while time.time() - start_time < duration_seconds:
        iteration += 1
        elapsed = int(time.time() - start_time)
        print(f"\n[{elapsed:2d}s] --- Check #{iteration} ---")

        for model_name, job_id in JOB_IDS.items():
            try:
                # Get job status
                resp = requests.get(f"{BASE_URL}/training/jobs/{job_id}")
                if resp.status_code != 200:
                    print(f"  {model_name:15} ERROR: {resp.status_code}")
                    continue

                job_data = resp.json()
                status = job_data.get("status")
                epoch = job_data.get("current_epoch", 0)
                total_epochs = job_data.get("total_epochs", 1)

                # Get metrics
                resp_metrics = requests.get(f"{BASE_URL}/training/jobs/{job_id}/metrics")
                metric_count = 0
                last_acc = None
                if resp_metrics.status_code == 200:
                    metrics = resp_metrics.json()
                    metric_count = len(metrics)
                    if metrics:
                        last_metric = metrics[-1]
                        last_acc = last_metric.get("val_acc", 0)

                # Format status line
                progress = f"{epoch}/{total_epochs}"
                status_str = f"{status:8} | E:{progress:5}"
                if last_acc is not None:
                    status_str += f" | Acc:{last_acc:.3f}"
                status_str += f" | Metrics:{metric_count}"

                print(f"  {model_name:15} {status_str}")

            except Exception as e:
                print(f"  {model_name:15} EXCEPTION: {str(e)[:40]}")

        if iteration * interval < duration_seconds:
            time.sleep(interval)

    print("\n" + "=" * 70)
    print(f"End time: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    monitor_jobs(duration_seconds=120, interval=5)
