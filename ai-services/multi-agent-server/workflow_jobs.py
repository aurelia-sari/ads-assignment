"""One bounded background queue for the shared cloud Multi-Agent process."""

import logging
from queue import Full, Queue
from threading import Lock, Thread


class QueueUnavailable(Exception):
    """The shared worker has no capacity to accept another workflow."""


class WorkflowQueue:
    """Run whole workflows sequentially so one model is shared predictably.

    The queue only owns execution; workflow state and the audit stay in store.
    Its daemon cannot block a systemd restart. Startup recovery marks unfinished
    persisted workflows as interrupted instead of silently replaying decisions.
    """

    def __init__(self, max_pending=8):
        if max_pending < 1:
            raise ValueError("max_pending must be positive")
        self._pending = Queue(maxsize=max_pending)
        self._lock = Lock()
        self._closed = False
        self._thread = Thread(target=self._run, name="nextstop-multi-agent", daemon=True)
        self._thread.start()

    def submit(self, action):
        with self._lock:
            if self._closed:
                raise QueueUnavailable("The shared workflow worker is shutting down; retry later.")
            try:
                self._pending.put_nowait(action)
            except Full as exc:
                raise QueueUnavailable("The shared workflow queue is full; retry later.") from exc

    def _run(self):
        while True:
            action = self._pending.get()
            try:
                if action is None:
                    return
                action()
            except Exception:
                # A failed callback must not disable processing for every user.
                logging.getLogger(__name__).exception("Shared workflow callback failed")
            finally:
                self._pending.task_done()

    def wait(self):
        """Wait for accepted jobs, used during orderly shutdown and tests."""
        self._pending.join()

    def shutdown(self):
        """Finish accepted work then stop the worker (normal tests/teardown)."""
        with self._lock:
            send_stop = not self._closed
            self._closed = True
        if send_stop:
            self._pending.put(None)
        self._thread.join()
