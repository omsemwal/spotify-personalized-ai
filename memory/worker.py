"""Why this file exists
=====================

The worker loop: read accepted events off the queue, turn them into
memories, and keep going even when one pass fails.

abc.md:188 - "A memory processor classifies the event, extracts candidate
facts into a typed schema, resolves canonical content and concept
entities, and applies minimization and sensitivity rules."

It can run in two places, with the same code:

    its own process    python scripts/run_processor.py --forever
                       (locally, and on any host with background workers)
    inside the API     RUN_WORKER_IN_API=true - a background thread started
                       by memory/startup.py, for a free host that offers only
                       one web service and no separate worker

Where it is used
----------------
scripts/run_processor.py - the command line.
memory/startup.py - the in-API thread.
"""

import os
import threading
import time

from memory import processor


# Run one pass and print what happened.
def one_pass() -> dict:
    outcome = processor.run_once()
    print(
        f"handled {outcome['handled']}, "
        f"failed {outcome['failed']}, "
        f"memories stored {outcome['memories_stored']}",
        flush=True,
    )
    return outcome


# Keep running passes; one failed pass must not stop the worker.
def run_forever(run_pass=one_pass, sleep=time.sleep, max_passes=None) -> None:
    """A pass can fail for reasons outside our code - on Windows the Kafka
    client's network thread sometimes dies with WinError 10038 while a
    consumer closes. If that ended the worker, events would keep being
    accepted and no memory would ever appear. Retrying is safe: each message
    is committed only after its work is done, so the next pass resumes from
    the first unfinished one.
    """
    passes = 0
    while max_passes is None or passes < max_passes:
        passes += 1
        try:
            outcome = run_pass()
        except Exception as exc:  # noqa: BLE001 - log it and try again
            print(f"pass failed, retrying in 5s: {type(exc).__name__}: {exc}", flush=True)
            sleep(5)
            continue
        # Nothing waiting: pause rather than spin.
        if outcome["handled"] == 0 and outcome["failed"] == 0:
            sleep(5)


# Is the worker meant to run inside the API process?
def runs_in_api() -> bool:
    # Forgiving on purpose: a value typed into a dashboard as "true" (with
    # quotes) or True or " yes " still counts.
    value = os.environ.get("RUN_WORKER_IN_API", "").strip().strip("\"'").strip().lower()
    return value in ("1", "true", "yes", "on")


# Start the worker as a background thread of this process.
def start_in_background() -> threading.Thread:
    """A daemon thread, so it stops when the API stops. One per process."""
    thread = threading.Thread(target=run_forever, name="memory-worker", daemon=True)
    thread.start()
    print("processor running inside the API (RUN_WORKER_IN_API)", flush=True)
    return thread
