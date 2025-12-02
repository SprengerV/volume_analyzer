import requests

RPC = "https://api.mainnet-beta.solana.com"

def rpc(method, params):
    payload = {"jsonrpc":"2.0","id":1,"method":method,"params":params}
    r = requests.post(RPC, json=payload).json()
    return r["result"]

def get_signatures(address, limit=100):
    return rpc("getSignaturesForAddress", [address, {"limit": limit}])

def get_transaction(signature):
    return rpc("getTransaction", [signature, "jsonParsed"])

