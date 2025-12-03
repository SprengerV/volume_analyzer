# live_monitor.py (PATCHED)
import threading
import time
from solana_rpc import get_signatures_for_address, get_transaction
from analysis_engine import parse_swap_from_tx
from datetime import datetime

class LiveMonitor:

    def __init__(self, address, on_event=None, poll_interval=15, history=25, silence_threshold_sec=240):
        self.address = address
        self.poll_interval = poll_interval
        self.on_event = on_event
        self.history = history
        self.silence_threshold = silence_threshold_sec
        self._stop = threading.Event()
        self._thread = None
        self.last_seen = None
        self.last_activity = None

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

    def _emit(self, etype, payload):
        if self.on_event:
            self.on_event(etype, payload)

    def _run(self):
        try:
            first = get_signatures_for_address(self.address, limit=1)
            if first:
                self.last_seen = first[0]["signature"]
        except:
            pass

        while not self._stop.is_set():
            try:
                metas = get_signatures_for_address(self.address, limit=self.history)
                if metas:
                    latest = metas[0]["signature"]
                    new = []

                    if self.last_seen:
                        for m in metas:
                            if m["signature"] == self.last_seen:
                                break
                            new.append(m)
                    else:
                        new = metas

                    for tx_meta in reversed(new):
                        sig = tx_meta["signature"]
                        tx = get_transaction(sig)
                        swaps = parse_swap_from_tx(tx)
                        if swaps:
                            self.last_activity = datetime.utcnow()
                            for s in swaps:
                                self._emit("BOT_ACTIVITY", {"swap": s})
                        time.sleep(0.15)

                    self.last_seen = latest

                # Silence
                if self.last_activity:
                    delta = (datetime.utcnow() - self.last_activity).total_seconds()
                    if delta > self.silence_threshold:
                        self._emit("BOT_SILENCE", {"since_sec": int(delta)})

            except Exception as e:
                self._emit("ERROR", {"error": str(e)})

            for _ in range(self.poll_interval):
                if self._stop.is_set():
                    break
                time.sleep(1)
