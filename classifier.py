# classifier.py

def classify_behavior(stats):
    """
    stats is a dict with:
      - wash: 0..1
      - rotation: 0..1
      - dominance: 0..1
      - net: numeric (positive means net buy)
      - unique_wallets_ratio: 0..1 (independent participation)
    """

    wash = stats.get("wash", 0)
    rotation = stats.get("rotation", 0)
    dominance = stats.get("dominance", 0)
    net = stats.get("net", 0)
    unique_ratio = stats.get("unique_wallets_ratio", 0)

    # Prioritize strong signals
    if dominance > 0.5 and net < -0.05:
        return "Exit Liquidity Bot"
    if wash > 0.7 and rotation > 0.6:
        return "Visibility / Fake Volume Bot"
    if rotation < 0.25 and dominance > 0.4 and abs(net) < 0.02:
        return "Price Anchor Bot"
    if dominance > 0.3 and net > 0.05 and unique_ratio > 0.2:
        return "Ignition Bot"
    if unique_ratio > 0.5 and dominance < 0.2:
        return "Organic"
    return "Mixed / Unknown"
