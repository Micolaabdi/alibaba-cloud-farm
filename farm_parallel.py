#!/usr/bin/env python3
"""
Parallel farm wrapper — spawns N Camoufox workers in parallel.
Each worker runs farm.py with a subset of the target count.

Usage:
  python farm_parallel.py                  # reads WORKERS + MAX_ATTEMPTS env
  python farm_parallel.py --workers 3 --count 15

Env vars (inherited from parent, set by dashboard API):
  WORKERS       — number of parallel Camoufox instances (default 1)
  MAX_ATTEMPTS  — total accounts to farm (default 20)
  EMAIL_DOMAIN  — catch-all domain
  IMAP_USER     — Gmail address
  IMAP_PASS     — Gmail app password

Each worker writes to results_worker_{i}.json.
On completion, all worker results are merged into results.json.
"""

import sys
import os
import json
import time
import math
import subprocess
import argparse
from pathlib import Path

# ─ Config ─
SCRIPT_DIR = Path(__file__).resolve().parent
FARM_SCRIPT = str(SCRIPT_DIR / "farm.py")
RESULTS_FILE = str(SCRIPT_DIR / "results.json")
STATUS_FILE = Path.home() / ".atmo-proxy" / "farm_alibaba_status.json"

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(str(SCRIPT_DIR / ".env"))
except ImportError:
    pass


def log(msg):
    """Print with timestamp — goes to stdout (captured by AtmoProxy log)."""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [PARALLEL] {msg}", flush=True)


def merge_worker_results():
    """Merge all results_worker_*.json into results.json."""
    merged = []
    # Load existing results
    try:
        with open(RESULTS_FILE) as f:
            merged = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Collect worker results
    worker_files = sorted(SCRIPT_DIR.glob("results_worker_*.json"))
    new_accounts = 0
    for wf in worker_files:
        try:
            with open(wf) as f:
                worker_data = json.load(f)
            for entry in worker_data:
                # Deduplicate by email
                email = entry.get("email", "")
                if not any(e.get("email") == email for e in merged):
                    merged.append(entry)
                    new_accounts += 1
        except Exception as e:
            log(f"Error reading {wf.name}: {e}")

    # Save merged results
    with open(RESULTS_FILE, "w") as f:
        json.dump(merged, f, indent=2)

    # Clean up worker files
    for wf in worker_files:
        try:
            wf.unlink()
        except Exception:
            pass

    log(f"Merged {new_accounts} new accounts into results.json (total: {len(merged)})")
    return new_accounts, len(merged)


def run_worker(worker_id, count_for_this_worker, env):
    """Run a single farm.py worker process."""
    worker_results = str(SCRIPT_DIR / f"results_worker_{worker_id}.json")
    worker_env = env.copy()
    worker_env["MAX_ATTEMPTS"] = str(count_for_this_worker)
    worker_env["RESULTS_FILE"] = worker_results

    # Use a separate Xvfb display per worker to avoid conflicts (Linux only)
    # On Windows, no Xvfb needed — Camoufox uses the real desktop
    if sys.platform == "win32":
        cmd = [sys.executable, "-u", FARM_SCRIPT]
    else:
        display = 99 + worker_id
        cmd = [
            "xvfb-run",
            "-a",
            "--server-num=" + str(display),
            sys.executable,
            "-u",
            FARM_SCRIPT,
        ]

    if sys.platform == "win32":
        log(f"Worker {worker_id}: starting (target={count_for_this_worker}, mode=windows)")
    else:
        log(f"Worker {worker_id}: starting (target={count_for_this_worker}, display=:{display})")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(SCRIPT_DIR),
            env=worker_env,
        )
        return proc
    except Exception as e:
        log(f"Worker {worker_id}: FAILED to start: {e}")
        return None


def monitor_workers(procs, total_target):
    """Monitor all worker processes, stream their output, count successes."""
    import threading

    all_done = 0
    all_failed = 0
    worker_results = {}  # worker_id -> (done, failed)

    def stream_worker(worker_id, proc):
        nonlocal all_done, all_failed
        for line in iter(proc.stdout.readline, b""):
            line = line.decode("utf-8", errors="replace").rstrip()
            # Prefix worker output
            print(f"[W{worker_id}] {line}", flush=True)
            # Count successes
            if "SUCCESS! Total accounts:" in line:
                all_done += 1
            if "❌" in line and "ATTEMPT" not in line:
                all_failed += 1
        proc.wait()
        log(f"Worker {worker_id}: exited (rc={proc.returncode})")

    threads = []
    for wid, proc in procs.items():
        if proc:
            t = threading.Thread(target=stream_worker, args=(wid, proc))
            t.daemon = True
            t.start()
            threads.append(t)

    # Wait for all workers
    for t in threads:
        t.join()

    return all_done, all_failed


def main():
    parser = argparse.ArgumentParser(description="Parallel Alibaba Cloud farm")
    parser.add_argument("--workers", type=int, default=None,
                        help="Number of parallel Camoufox instances")
    parser.add_argument("--count", type=int, default=None,
                        help="Total accounts to farm")
    args = parser.parse_args()

    # Resolve config from args or env
    workers = args.workers or int(os.environ.get("WORKERS", "1"))
    total_count = args.count or int(os.environ.get("MAX_ATTEMPTS", "20"))

    # Clamp workers
    workers = max(1, min(workers, 5))
    total_count = max(1, min(total_count, 200))

    # Distribute count across workers
    # Each worker gets ceil(total/workers) but we adjust so sum = total
    per_worker = math.ceil(total_count / workers)
    counts = []
    remaining = total_count
    for i in range(workers):
        c = min(per_worker, remaining)
        counts.append(c)
        remaining -= c
    # Ensure all accounted for
    if remaining > 0:
        counts[-1] += remaining

    log(f"=== Parallel Farm ===")
    log(f"Workers: {workers}")
    log(f"Total target: {total_count}")
    for i, c in enumerate(counts):
        log(f"  Worker {i}: {c} accounts")
    log(f"Domain: {os.environ.get('EMAIL_DOMAIN', '?')}")
    log(f"")

    # Count existing results
    try:
        with open(RESULTS_FILE) as f:
            existing_count = len(json.load(f))
    except Exception:
        existing_count = 0
    log(f"Existing accounts in results.json: {existing_count}")

    # Build env for workers
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    # Start all workers
    procs = {}
    for i in range(workers):
        proc = run_worker(i, counts[i], env)
        if proc:
            procs[i] = proc
        # Small stagger to avoid resource contention
        if i < workers - 1:
            time.sleep(2)

    if not procs:
        log("ERROR: No workers started!")
        sys.exit(1)

    # Monitor all workers
    done, failed = monitor_workers(procs, total_count)

    log(f"")
    log(f"=== All workers finished ===")
    log(f"Successes: {done}")
    log(f"Failures: {failed}")

    # Merge results
    new_count, total_count_after = merge_worker_results()

    # Update status file
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        status = {}
        if STATUS_FILE.exists():
            status = json.loads(STATUS_FILE.read_text())
        status["status"] = "done" if new_count > 0 else "error"
        status["done"] = new_count
        status["failed"] = failed
        status["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        status["workers"] = workers
        STATUS_FILE.write_text(json.dumps(status, indent=2))
        log(f"Status file updated: {status['status']} ({new_count} new accounts)")
    except Exception as e:
        log(f"Warning: failed to update status file: {e}")

    log(f"Total accounts in results.json: {total_count_after}")
    log(f"=== DONE ===")


if __name__ == "__main__":
    main()
