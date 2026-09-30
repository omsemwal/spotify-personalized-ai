"""Why this file exists
=====================

Runs the memory processor: reads accepted events off the queue and turns
them into stored memories.

    python scripts/run_processor.py           one pass, then stop
    python scripts/run_processor.py --forever keep going

abc.md:188 - "A memory processor classifies the event, extracts candidate
facts into a typed schema, resolves canonical content and concept
entities, and applies minimization and sensitivity rules."
abc.md:257 lists memory-processor as one of the six services.

Without this running, events are captured but never become memories.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory import processor  # noqa: E402


# Run one pass and print what happened.
def one_pass() -> dict:
    outcome = processor.run_once()
    print(
        f"handled {outcome['handled']}, "
        f"failed {outcome['failed']}, "
        f"memories stored {outcome['memories_stored']}"
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
            print(f"pass failed, retrying in 5s: {type(exc).__name__}: {exc}")
            sleep(5)
            continue
        # Nothing waiting: pause rather than spin.
        if outcome["handled"] == 0 and outcome["failed"] == 0:
            sleep(5)


if __name__ == "__main__":
    if "--forever" in sys.argv:
        print("processor running, Ctrl+C to stop")
        try:
            run_forever()
        except KeyboardInterrupt:
            print("stopped")
    else:
        one_pass()
