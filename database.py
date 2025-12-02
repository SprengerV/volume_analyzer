import sqlite3

DB = "analyses.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE,
        classification TEXT,
        report TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

def save_analysis(token, classification, report):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO analyses (token, classification, report) VALUES (?, ?, ?)",
              (token, classification, report))
    conn.commit()
    conn.close()

def load_tokens():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT token FROM analyses")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def load_analysis(token):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT classification, report FROM analyses WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()
    return row

def delete_token(token):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM analyses WHERE token = ?", (token,))
    conn.commit()
    conn.close()
