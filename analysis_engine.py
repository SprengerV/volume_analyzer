# analysis_engine.py
import time
import pandas as pd
from solana_rpc import get_signatures_for_address, get_transaction
from classifier import classify_behavior
from datetime import datetime, timedelta
from collections import defaultdict

# Known DEX program ids common on Solana (this list is not exhaustive)
DEX_PROGRAMS = {
    # Raydium AMM
    "amm": "RVKd61ztZW9G2pQGxQkzD8W8rU7p6y3Z7vihT4qf7WAX",  # placeholder; Raydium program id sometimes changes with forks; we'll primarily use program name parsing
    "orca": "9W7o4Z3w5g2k2iP3V3...".lower(),  # placeholder - we won't rely on exact ids alone
}

def _normalize_token_amount(balance_entry):
    """
    balance_entry is from preTokenBalances/postTokenBalances
    returns (mint, amount_float, decimals)
    """
    if not balance_entry:
        return None
    mint = balance_entry.get("mint")
    ui_amount = balance_entry.get("uiTokenAmount", {})
    amount = ui_amount.get("uiAmount")
    decimals = ui_amount.get("decimals")
    return {"mint": mint, "amount": amount, "decimals": decimals}

def parse_swap_from_tx(tx_json):
    """
    Parses a single parsed tx JSON (getTransaction response) to find swaps/transfers and compute
    amounts in/out. Returns a list of swap summaries (can be empty).
    """
    if not tx_json:
        return []
    meta = tx_json.get("meta", {})
    if meta.get("err"):
        return []  # skip failed txs

    pre = meta.get("preTokenBalances", []) or []
    post = meta.get("postTokenBalances", []) or []
    # map by account index to token balance object
    pre_map = {p.get("accountIndex"): p for p in pre}
    post_map = {p.get("accountIndex"): p for p in post}

    message = tx_json.get("transaction", {}).get("message", {})
    account_keys = message.get("accountKeys", [])

    # helper to get signer/fee payer
    sigs = tx_json.get("transaction", {}).get("signatures", [])

    ts = tx_json.get("blockTime")
    ts_iso = datetime.utcfromtimestamp(ts).isoformat() if ts else None

    swaps = []
    # We will look at instructions and innerInstructions
    # For each instruction, if parsed.type indicates a 'swap' or program contains 'swap', try to reason token flows
    instructions = message.get("instructions", []) or []
    inner_instructions = meta.get("innerInstructions", []) or []

    all_instructions = []
    all_instructions.extend(instructions)
    for inner in inner_instructions:
        for i in inner.get("instructions", []):
            all_instructions.append(i)

    # find token changes by comparing pre/post balances per mint per owner
    # Build a map: mint -> (sum pre, sum post)
    mint_changes = defaultdict(lambda: {"pre": 0.0, "post": 0.0, "decimals": None})
    for p in pre:
        mint = p.get("mint")
        ui = p.get("uiTokenAmount", {})
        amt = ui.get("uiAmount") or 0
        mint_changes[mint]["pre"] += amt
        mint_changes[mint]["decimals"] = ui.get("decimals")
    for p in post:
        mint = p.get("mint")
        ui = p.get("uiTokenAmount", {})
        amt = ui.get("uiAmount") or 0
        mint_changes[mint]["post"] += amt
        mint_changes[mint]["decimals"] = ui.get("decimals")

    # Attempt to infer swaps by looking for meaningful token amount decreases/increases in same tx
    # Heuristic: token A decreased, token B increased by non-trivial amounts -> swap occurred
    for mint, vals in mint_changes.items():
        delta = vals["post"] - vals["pre"]
        mint_changes[mint]["delta"] = delta

    # collect candidate swap mints: those with negative delta and positive delta counterpart
    negatives = [(m, v["delta"]) for m, v in mint_changes.items() if v["delta"] < -1e-9]
    positives = [(m, v["delta"]) for m, v in mint_changes.items() if v["delta"] > 1e-9]

    # if both exist, create swap summaries for each negative->positive pairing (simple)
    for neg_mint, neg_amt in negatives:
        for pos_mint, pos_amt in positives:
            # compute naive price: pos_amt / -neg_amt
            try:
                price = pos_amt / (-neg_amt)
            except Exception:
                price = None
            swaps.append({
                "ts": ts_iso,
                "mint_in": neg_mint,
                "amount_in": -neg_amt,
                "mint_out": pos_mint,
                "amount_out": pos_amt,
                "price": price,
                "programs": [instr.get("program") for instr in all_instructions if instr.get("program")],
                "raw": tx_json
            })
    return swaps

def analyze_token(address, lookback=200):
    """
    Fetch last `lookback` signatures for the address and compute stats and classification.
    Returns classification, report, dataframe of parsed swaps.
    """
    sigs_meta = get_signatures_for_address(address, limit=lookback)
    if not sigs_meta:
        return "No data", "No signatures found", None

    signatures = [s["signature"] for s in sigs_meta]
    parsed_swaps = []
    parsed_tx_count = 0

    for sig in signatures:
        tx = get_transaction(sig)
        parsed = parse_swap_from_tx(tx)
        if parsed:
            parsed_swaps.extend(parsed)
        parsed_tx_count += 1
        # light rate-limit
        time.sleep(0.12)

    # Build a dataframe for swaps
    if parsed_swaps:
        df = pd.DataFrame(parsed_swaps)
    else:
        # empty df with expected columns
        df = pd.DataFrame(columns=["ts","mint_in","amount_in","mint_out","amount_out","price","programs","raw"])

    # compute stats
    now = datetime.utcnow()
    window_minutes = 60
    window_cutoff = now - timedelta(minutes=window_minutes)
    recent_df = df[df.ts.astype('datetime64[ns]') >= pd.to_datetime(window_cutoff)] if not df.empty else df

    total_swaps = len(df)
    recent_swaps = len(recent_df)
    # dominance: fraction of swaps in recent window over lookback (simple proxy)
    dominance = (recent_swaps / max(1, total_swaps)) if total_swaps > 0 else 0.0

    # wash detection: detect quick buy then sell cycles in tx list by raw details:
    wash_count = 0
    # naive: if same mint appears both as in and out within a short sequence
    mint_in_sequence = []
    for _,row in df.iterrows():
        mint_in_sequence.append((row["mint_in"], row["mint_out"], row["ts"]))

    # quick heuristic wash detection
    for i, (mint_in, mint_out, ts) in enumerate(mint_in_sequence):
        # check next N entries for reverse
        for j in range(i+1, min(i+6, len(mint_in_sequence))):
            if mint_in_sequence[j][0] == mint_out and mint_in_sequence[j][1] == mint_in:
                wash_count += 1

    wash_score = wash_count / max(1, total_swaps)

    # rotation: how many distinct account keys used as signers/fee-payers across txs
    # We'll approximate rotation by counting distinct fee-payer accounts from raw tx
    fee_payers = set()
    unique_wallets = set()
    for _,row in df.iterrows():
        raw = row.get("raw") or {}
        tx_msg = raw.get("transaction", {}).get("message", {})
        keys = tx_msg.get("accountKeys", [])
        # accountKeys entries could be dicts or strings depending on RPC version; handle both
        for k in keys:
            if isinstance(k, dict):
                pub = k.get("pubkey")
                if pub:
                    unique_wallets.add(pub)
            elif isinstance(k, str):
                unique_wallets.add(k)
    rotation_score = 1.0 - (len(unique_wallets)/max(1, total_swaps)) if total_swaps>0 else 0.0
    # normalize rotation into 0..1 where higher means more rotation (more distinct wallets)
    rotation_score = min(1.0, len(unique_wallets)/max(1, total_swaps))

    # net flow by mint: compute sign of sum(amount_in - amount_out) per mint (as relative)
    net_by_mint = {}
    for _,row in df.iterrows():
        mint_in = row["mint_in"]
        amt_in = float(row["amount_in"]) if row["amount_in"] else 0
        mint_out = row["mint_out"]
        amt_out = float(row["amount_out"]) if row["amount_out"] else 0
        net_by_mint[mint_in] = net_by_mint.get(mint_in, 0.0) - amt_in
        net_by_mint[mint_out] = net_by_mint.get(mint_out, 0.0) + amt_out

    # compute a crude 'net' normalized value: max absolute net divided by total volume
    total_volume = sum(abs(v) for v in net_by_mint.values()) or 1
    # We take the sign of the most traded mint as a proxy
    if net_by_mint:
        top_mint = max(net_by_mint.items(), key=lambda x: abs(x[1]))[0]
        net = net_by_mint[top_mint] / total_volume
    else:
        net = 0.0

    # unique wallet participation ratio: number of unique wallets in recent window / total wallets observed
    unique_wallets_recent = len(unique_wallets)
    unique_wallets_ratio = unique_wallets_recent / max(1, total_swaps)

    stats = {
        "total_swaps": total_swaps,
        "recent_swaps": recent_swaps,
        "dominance": dominance,
        "wash": min(1.0, wash_score),
        "rotation": rotation_score,
        "net": net,
        "unique_wallets_ratio": min(1.0, unique_wallets_ratio)
    }

    classification = classify_behavior(stats)

    # Construct human readable report
    report = f"""Classification: {classification}
Total swaps parsed: {total_swaps}
Recent swaps (last {window_minutes}m): {recent_swaps}
Dominance (recent/total): {dominance:.3f}
Wash score: {stats['wash']:.3f}
Rotation score: {stats['rotation']:.3f}
Net proxy: {stats['net']:.3f}
Unique wallets ratio: {stats['unique_wallets_ratio']:.3f}
"""

    return classification, report, df, stats
