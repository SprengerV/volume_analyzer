# solana_rpc.py (PATCHED)
import requests, time, random

# You can rotate between multiple endpoints (add Helius/Alchemy/QuickNode here)
RPC_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    # EXAMPLE PAID ENDPOINTS (UNCOMMENT AND ADD KEYS)
    # "https://rpc.helius.xyz/?api-key=YOUR_KEY",
    # "https://solana-mainnet.g.alchemy.com/v2/YOUR_KEY",
]

REQUEST_TIMEOUT = 20
MAX_RETRIES = 5

def _pick_rpc():
    return random.choice(RPC_ENDPOINTS)

def rpc(method, params):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

    for attempt in range(MAX_RETRIES):
        rpc_url = _pick_rpc()
        try:
            r = requests.post(rpc_url, json=payload, timeout=REQUEST_TIMEOUT)

            if r.status_code == 429:
                sleep = 1.5 * (attempt + 1)
                time.sleep(sleep)
                continue

            r.raise_for_status()
            js = r.json()
            if "error" in js:
                raise RuntimeError(js["error"])

            return js["result"]

        except requests.exceptions.RequestException as e:
            time.sleep(1 + attempt * 1.5)

    raise Exception("All RPC endpoints failed after multiple attempts")

def get_signatures_for_address(address, before=None, limit=50):
    opts = {"limit": limit}
    if before:
        opts["before"] = before
    return rpc("getSignaturesForAddress", [address, opts])

def get_transaction(signature):
    return rpc("getTransaction", [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
