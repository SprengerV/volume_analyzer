import tkinter as tk
from database import *
from analysis_engine import analyze_token

init_db()

def refresh_list():
    listbox.delete(0, tk.END)
    for t in load_tokens():
        listbox.insert(tk.END, t)

def analyze():
    token = entry.get()
    if not token: return

    classification, report = analyze_token(token)
    save_analysis(token, classification, report)
    refresh_list()
    output.delete("1.0", tk.END)
    output.insert(tk.END, report)

def load_selected():
    sel = listbox.get(tk.ACTIVE)
    res = load_analysis(sel)
    if res:
        output.delete("1.0", tk.END)
        output.insert(tk.END, res[1])

def delete_selected():
    sel = listbox.get(tk.ACTIVE)
    delete_token(sel)
    refresh_list()
    output.delete("1.0", tk.END)

root = tk.Tk()
root.title("Solana Volume Bot Analyzer")

entry = tk.Entry(root, width=50)
entry.pack()

tk.Button(root, text="Analyze", command=analyze).pack()

listbox = tk.Listbox(root, width=60)
listbox.pack()

tk.Button(root, text="Load", command=load_selected).pack()
tk.Button(root, text="Delete", command=delete_selected).pack()

output = tk.Text(root, height=24, width=80)
output.pack()

refresh_list()
root.mainloop()
