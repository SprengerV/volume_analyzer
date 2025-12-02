# app.py  (REPLACE ENTIRE FILE)
import tkinter as tk
from database import *
from analysis_engine import analyze_token
from live_monitor import LiveMonitor
import threading
import time
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

init_db()
monitors = {}

# ------------ GUI HELPERS -------------

def refresh_list():
    token_list.delete(0, tk.END)
    for t in load_tokens():
        token_list.insert(tk.END, t)

def set_status(text):
    status_label.config(text=text)

# ------------ ANALYZE BUTTON FIX -------------

def analyze_click():
    token = entry.get().strip()
    if not token:
        set_status("No address entered")
        return

    set_status("Analyzing...")
    output.delete("1.0", tk.END)

    def run():
        try:
            classification, report, df, stats = analyze_token(token)
            save_analysis(token, classification, report)

            output.delete("1.0", tk.END)
            output.insert(tk.END, report)

            refresh_list()
            plot_data(df)

            set_status("Analysis complete")

        except Exception as e:
            output.insert(tk.END, f"ERROR: {str(e)}\n")
            set_status("Error")

    threading.Thread(target=run, daemon=True).start()

# ------------ PLOTTING FUNCTION -------------

def plot_data(df):
    ax1.clear()
    ax2.clear()

    if df is None or df.empty:
        ax1.set_title("No swap data")
        canvas.draw()
        return

    df['ts'] = df['ts'].astype('datetime64')
    df = df.sort_values("ts")

    times = df['ts']
    sizes = df['amount_out']
    prices = df['price'].fillna(0)

    ax1.plot(times, sizes)
    ax1.set_title("Swap Output Volume Over Time")
    ax1.set_ylabel("Amount Out")

    ax2.plot(times, prices)
    ax2.set_title("Effective Price (Proxy)")
    ax2.set_ylabel("Price (out/in)")

    fig.autofmt_xdate()
    canvas.draw()

# ------------ LIST FUNCTIONS -------------

def load_selected():
    try:
        token = token_list.get(token_list.curselection())
    except:
        return
    res = load_analysis(token)
    if res:
        classification, report = res
        output.delete("1.0", tk.END)
        output.insert(tk.END, report)
        set_status("Loaded")

def delete_selected():
    try:
        token = token_list.get(token_list.curselection())
    except:
        return
    delete_token(token)
    refresh_list()
    output.delete("1.0", tk.END)
    set_status("Deleted")

# ------------ LIVE MONITORING -------------

def start_monitor():
    address = entry.get().strip()
    if not address:
        return

    if address in monitors:
        set_status("Monitor already running")
        return

    def on_event(event, payload):
        def ui():
            if event == "BOT_ACTIVITY":
                s = payload["swap"]
                output.insert(tk.END,
                    f"[LIVE] {s['ts']} | {s['mint_in'][:6]}→{s['mint_out'][:6]} | {s['amount_out']:.4f}\n")
                output.see(tk.END)
            elif event == "BOT_SILENCE":
                output.insert(tk.END,
                    f"[SILENCE] No bot swaps for {payload['since_sec']} seconds\n")
            elif event == "ERROR":
                output.insert(tk.END, f"[ERROR] {payload['error']}\n")
        root.after(0, ui)

    monitor = LiveMonitor(address, on_event=on_event)
    monitors[address] = monitor
    monitor.start()
    set_status("Monitoring...")

def stop_monitor():
    address = entry.get().strip()
    mon = monitors.get(address)
    if mon:
        mon.stop()
        del monitors[address]
        set_status("Stopped")

# ------------ GUI LAYOUT -------------

root = tk.Tk()
root.title("Solana Volume Bot Analyzer")

# Entry Line
top = tk.Frame(root)
top.pack(pady=6)

tk.Label(top, text="Token CA / Wallet:").pack(side=tk.LEFT)
entry = tk.Entry(top, width=48)
entry.pack(side=tk.LEFT, padx=6)

tk.Button(top, text="Analyze", command=analyze_click).pack(side=tk.LEFT)
tk.Button(top, text="Start Monitor", command=start_monitor).pack(side=tk.LEFT, padx=4)
tk.Button(top, text="Stop Monitor", command=stop_monitor).pack(side=tk.LEFT)

# Token List
mid = tk.Frame(root)
mid.pack()

token_list = tk.Listbox(mid, width=50)
token_list.pack(side=tk.LEFT)

btns = tk.Frame(mid)
btns.pack(side=tk.LEFT, padx=6)
tk.Button(btns, text="Load", command=load_selected).pack(pady=2)
tk.Button(btns, text="Delete", command=delete_selected).pack(pady=2)

# Output Box
output = tk.Text(root, height=12, width=100)
output.pack()

# Status
status_label = tk.Label(root, text="Idle")
status_label.pack()

# ------------ MATPLOTLIB EMBEDDED CHART -------------

fig = Figure(figsize=(9, 4))
ax1 = fig.add_subplot(211)
ax2 = fig.add_subplot(212)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.draw()
canvas.get_tk_widget().pack()

refresh_list()
root.mainloop()
