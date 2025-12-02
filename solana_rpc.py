# solana_rpc.py
import requests, time

# Default public RPC. For reliability, substitute a paid RPC endpoint (QuickNode, Alchemy, etc.)
RPC = "https://api.mainnet-beta.solana.com"
REQUEST_TIMEOUT = 30

def rpc(method, params):
    payload = {"jsonrpc":"2.0","id":1,"method":method,"params":params}
    r = requests.post(RPC, json=payload, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    j = r.json()
    # basic error handling
    if "error" in j:
        raise RuntimeError(f"RPC Error: {j['error']}")
    return j.get("result")

def get_signatures_for_address(address, before=None, limit=100):
    opts = {"limit": limit}
    if before:
        opts["before"] = before
    return rpc("getSignaturesForAddress", [address, opts])

def get_transaction(signature):
    # request parsed transaction for easier instruction decoding
    return rpc("getTransaction", [signature, "jsonParsed"])

def get_recent_block_time():
    return rpc("getEpochInfo", [])


