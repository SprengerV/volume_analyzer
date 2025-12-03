# analysis_engine.py (PATCHED)
import time
import pandas as pd
from solana_rpc import get_signatures_for_address, get_transaction
from classifier import classify_behavior
from datetime import datetime, timedelta
from collections import defaultdict

MAX_TX_FETCH = 120   # hard cap to protect RPC

def parse_swap_from_tx(tx_json):
    if not tx_json or "meta" not in tx_json:
        return []

    meta = tx_json.get("meta")
    if meta.get("err"):
        return []

    ts = tx_json.get("blockTime")
    ts_iso = datetime.utcfromtimestamp(ts).isoformat() if ts else None

    pre = meta.get("preTokenBalances", []) or []
    post = meta.get("postTokenBalances", []) or []

    mint_changes = defaultdict(lambda: {"pre": 0.0, "post": 0.0})

    for p in pre:
        ui = p.get("uiTokenAmount", {})
        mint_changes[p.get("mint")]["pre"] += ui.get("uiAmount") or 0

    for p in post:
        ui = p.get("uiTokenAmount", {})
        mint_changes[p.get("mint")]["post"] += ui.get("uiAmount") or 0

    negatives = []
    positives = []

    for mint, v in mint_changes.items():
        delta = v["post"] - v["pre"]
        if delta < -1e-9:
            negatives.append((mint, delta))
        elif delta > 1e-9:
            positives.append((mint, delta))

    swaps = []
    for neg_mint, neg_amt in negatives:
        for pos_mint, pos_amt in positives:
            price = abs(pos_amt / neg_amt) if neg_amt != 0 else None
            swaps.append({
                "ts": ts_iso,
                "mint_in": neg_mint,
                "amount_in": abs(neg_amt),
                "mint_out": pos_mint,
                "amount_out": pos_amt,
                "price": price,
            })

    return swaps

def analyze_token(address, lookback=200):

    sigs = get_signatures_for_address(address, limit=min(lookback, MAX_TX_FETCH))
    if not sigs:
        return "No data", "No transactions found.", None, {}

    signatures = [s["signature"] for s in sigs][:MAX_TX_FETCH]

    all_swaps = []

    for sig in signatures:
        try:
            tx = get_transaction(sig)
            swaps = parse_swap_from_tx(tx)
            all_swaps.extend(swaps)
            time.sleep(0.18)  # throttle RPC
        except:
            continue

    if not all_swaps:
        return "No swaps", "No swap activity detected.", None, {}

    df = pd.DataFrame(all_swaps)
    df["ts"] = pd.to_datetime(df["ts"])
    df.sort_values("ts", inplace=True)

    now = datetime.utcnow()
    cutoff = now - timedelta(hours=1)

    recent = df[df["ts"] >= cutoff]

    total = len(df)
    recent_n = len(recent)

    dominance = recent_n / max(1, total)

    wash_count = 0
    seq = list(zip(df["mint_in"], df["mint_out"]))

    for i in range(len(seq)):
        for j in range(i+1, min(i+6, len(seq))):
            if seq[i] == tuple(reversed(seq[j])):
                wash_count += 1

    wash = wash_count / max(1, total)
    rotation = min(1.0, len(set(df["mint_in"])) / max(1, total))

    net_flow = df["amount_out"].sum() - df["amount_in"].sum()
    net = net_flow / max(1, df["amount_out"].sum())

    stats = {
        "wash": wash,
        "rotation": rotation,
        "dominance": dominance,
        "net": net,
        "unique_wallets_ratio": rotation
    }

    classification = classify_behavior(stats)

    report = f"""Classification: {classification}

Total Swaps Parsed: {total}
Recent Swaps (1h): {recent_n}
Dominance Score: {dominance:.3f}
Wash Score: {wash:.3f}
Rotation Score: {rotation:.3f}
Net Flow Proxy: {net:.3f}
"""

    return classification, report, df, stats
