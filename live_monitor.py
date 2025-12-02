# live_monitor.py
import threading
import time
from solana_rpc import get_signatures_for_address, get_transaction
from analysis_engine import parse_swap_from_tx
from datetime import datetime, timedelta

class LiveMonitor:
    """
    Polling-based live monitor for a single wallet/token.
    Usage:
      m = LiveMonitor(wallet, on_event=callback, poll_interval=8, history=200)
      m.start()
      m.stop()
    callback(event_type, payload) will be called in monitor thread.
    """

    def __init__(self, address, on_event=None, poll_interval=8, history=200, silence_threshold_sec=300):
        self.address = address
        self.poll_interval = poll_interval
        self.on_event = on_event
        self._stop = threading.Event()
        self._thread = None
        self.last_seen_sig = None
        self.history = history
        self.silence_threshold = silence_threshold_sec
        self._last_activity_time = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _emit(self, event_type, payload):
        if self.on_event:
            try:
                self.on_event(event_type, payload)
            except Exception as e:
                print("Callback error:", e)

    def _run(self):
        # initialize last_seen_sig with most recent if not set
        try:
            metas = get_signatures_for_address(self.address, limit=1)
            if metas:
                self.last_seen_sig = metas[0]["signature"]
        except Exception as e:
            print("Error initializing monitor:", e)

        while not self._stop.is_set():
            try:
                metas = get_signatures_for_address(self.address, limit=self.history)
                if metas:
                    newest = metas[0]["signature"]
                    # find index of last_seen_sig
                    new_sigs = []
                    if self.last_seen_sig:
                        for m in metas:
                            if m["signature"] == self.last_seen_sig:
                                break
                            new_sigs.append(m)
                    else:
                        new_sigs = metas

                    # process in reverse chronological order (old -> new)
                    for m in reversed(new_sigs):
                        sig = m["signature"]
                        tx = get_transaction(sig)
                        swaps = parse_swap_from_tx(tx)
                        if swaps:
                            # activity event
                            self._last_activity_time = datetime.utcnow()
                            for s in swaps:
                                self._emit("BOT_ACTIVITY", {"signature": sig, "swap": s})
                        # small sleep to respect public RPCs
                        time.sleep(0.08)

                    if newest != self.last_seen_sig:
                        self.last_seen_sig = newest
                # silence detection
                if self._last_activity_time:
                    delta = (datetime.utcnow() - self._last_activity_time).total_seconds()
                    if delta > self.silence_threshold:
                        self._emit("BOT_SILENCE", {"since_sec": int(delta)})
                else:
                    # if no activity ever observed, emit silence if monitor has been running longer than threshold
                    pass

            except Exception as e:
                # don't kill the monitor on RPC errors
                self._emit("ERROR", {"error": str(e)})
            # sleep until next poll
            for _ in range(max(1, int(self.poll_interval))):
                if self._stop.is_set(): break
                time.sleep(1)
