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


if __name__ == "__main__":
    if "--forever" in sys.argv:
        print("processor running, Ctrl+C to stop")
        try:
            while True:
                outcome = one_pass()
                # Nothing waiting: pause rather than spin.
                if outcome["handled"] == 0 and outcome["failed"] == 0:
                    time.sleep(5)
        except KeyboardInterrupt:
            print("stopped")
    else:
        one_pass()
