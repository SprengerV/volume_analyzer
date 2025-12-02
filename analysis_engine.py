from solana_rpc import get_signatures, get_transaction
from classifier import classify_behavior

def analyze_token(address):

    sigs = get_signatures(address, limit=200)
    txs = []

    for sig in sigs:
        tx = get_transaction(sig["signature"])
        if tx:
            txs.append(tx)

    # Placeholder heuristics (replace with real parsers)
    stats = {
        "wash": sum(1 for t in txs if "swap" in str(t).lower()) / len(txs),
        "rotation": len(set(str(t) for t in txs)) / len(txs),
        "dominance": len(txs) / 200,
        "net": 0   # Extend this: token inflows vs outflows
    }

    classification = classify_behavior(stats)

    report = f"""
Classification: {classification}

Wash Score: {stats['wash']:.2f}
Rotation Score: {stats['rotation']:.2f}
Bot Dominance: {stats['dominance']:.2f}

Notes:
- High synthetic activity detected
- Repetitive patterns consistent with automation
- Treat volume with caution

Strategy:
- Don't chase breakouts
- Wait for bot silence
- Trade reaction not action
"""

    return classification, report
