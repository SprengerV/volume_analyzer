def classify_behavior(stats):

    wash = stats["wash"]
    rotation = stats["rotation"]
    dominance = stats["dominance"]
    net = stats["net"]

    if wash > 0.75 and rotation > 0.7:
        return "Visibility / Fake Volume Bot"

    if dominance > 0.5 and net < 0:
        return "Exit Liquidity Bot"

    if wash < 0.3 and rotation < 0.3 and dominance > 0.4:
        return "Price Anchor Bot"

    if dominance > 0.3 and net > 0 and wash > 0.5:
        return "Ignition Bot"

    return "Organic / Mixed"
