# app.py
import tkinter as tk
from database import *
from analysis_engine import analyze_token
from live_monitor import LiveMonitor
from solana_rpc import get_signatures_for_address
import threading
import json

init_db()

monitors = {}  # address -> LiveMonitor

def start_monitor(address, output_widget, status_label):
    if address in monitors:
        status_label.config(text="Monitor already running")
        return
    def on_event(event_type, payload):
        # Called from monitor thread; use thread-safe insert via tkinter's `after`
        def ui_update():
            if event_type == "BOT_ACTIVITY":
                s = payload["swap"]
                out = f"[{s['ts']}] SWAP {s['mint_in'][:8]} -> {s['mint_out'][:8]} | in:{s['amount_in']:.6f} out:{s['amount_out']:.6f} price:{s.get('price')}\n"
                output_widget.insert(tk.END, out)
                # auto-scroll
                output_widget.see(tk.END)
            elif event_type == "BOT_SILENCE":
                output_widget.insert(tk.END, f"[SILENCE] Bot silent for {payload['since_sec']}s\n")
                output_widget.see(tk.END)
            elif event_type == "ERROR":
                output_widget.insert(tk.END, f"[ERROR] {payload['error']}\n")
                output_widget.see(tk.END)
        output_widget.after(0, ui_update)
    monitor = LiveMonitor(address, on_event=on_event, poll_interval=8, history=200, silence_threshold_sec=240)
    monitors[address] = monitor
    monitor.start()
    status_label.config(text="Monitoring")

def stop_monitor(address, status_label):
    mon = monitors.get(address)
    if not mon:
        status_label.config(text="Not running")
        return
    mon.stop()
    del monitors[address]
    status_label.config(text="Stopped")

# GUI
root = tk.Tk()
root.title("Solana Volume Bot Analyzer — Live")

frame_top = tk.Frame(root)
frame_top.pack(pady=6)

tk.Label(frame_top, text="Token / Wallet CA:").pack(side=tk.LEFT)
entry = tk.Entry(frame_top, width=48)
entry.pack(side=tk.LEFT, padx=6)
analyze_btn = tk.Button(frame_top, text="Analyze", width=10)
analyze_btn.pack(side=tk.LEFT, padx=4)

frame_mid = tk.Frame(root)
frame_mid.pack()

listbox = tk.Listbox(frame_mid, width=60)
listbox.pack(side=tk.LEFT, padx=6, pady=6)

btn_frame = tk.Frame(frame_mid)
btn_frame.pack(side=tk.LEFT, padx=6)
tk.Button(btn_frame, text="Load", width=10, command=lambda: load_selected()).pack(pady=4)
tk.Button(btn_frame, text="Delete", width=10, command=lambda: delete_selected()).pack(pady=4)

frame_monitor = tk.Frame(root)
frame_monitor.pack(pady=6)

status_label = tk.Label(frame_monitor, text="Idle")
status_label.pack()

output = tk.Text(root, height=20, width=100)
output.pack()

def refresh_list():
    listbox.delete(0, tk.END)
    for t in load_tokens():
        listbox.insert(tk.END, t)

def analyze_click():
    token = entry.get().strip()
    if not token:
        return
    analyze_btn.config(text="Working...")
    def run_analysis():
        classification, report, df, stats = analyze_token(token)
        save_analysis(token, classification, report)
        output.delete("1.0", tk.END)
        output.insert(tk.END, report)
        refresh_list()
        analyze_btn.config(text="Analyze")
    threading.Thread(target=run_analysis, daemon=True).start()

def load_selected():
    try:
        sel = listbox.get(listbox.curselection())
    except:
        return
    res = load_analysis(sel)
    if res:
        classification, report = res
        output.delete("1.0", tk.END)
        output.insert(tk.END, report)

def delete_selected():
    try:
        sel = listbox.get(listbox.curselection())
    except:
        return
    delete_token(sel)
    refresh_list()
    output.delete("1.0", tk.END)

tk.Button(frame_top, text="Start Monitor", command=lambda: start_monitor(entry.get().strip(), output, status_label)).pack(side=tk.RIGHT, padx=6)
tk.Button(frame_top, text="Stop Monitor", command=lambda: stop_monitor(entry.get().strip(), status_label)).pack(side=tk.RIGHT)

tk.Button(root, text="Export Last Output", command=lambda: export_output()).pack(pady=4)

def export_output():
    data = output.get("1.0", tk.END)
    name = f"monitor_output_{int(time.time())}.txt"
    with open(name, "w", encoding="utf-8") as f:
        f.write(data)
    output.insert(tk.END, f"\nSaved to {name}\n")

refresh_list()
root.mainloop()
