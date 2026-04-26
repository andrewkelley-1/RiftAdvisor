import json
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"

def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

items_data = load_json(DATA_DIR / "items.json")
champion_data = load_json(DATA_DIR / "champions.json")

ITEM_BLACKLIST = {
    "The Golden Spatula",
    "Wooglet's Witchcap", 
    "Deathfire Grasp",
    "Void Immolation",
}

# -------------------------------------------------------
# Map champion class tags to relevant item tags
# A champion can have multiple classes so we union the sets
# -------------------------------------------------------
# Map champion class to the STAT KEYS that must be present in the item
CLASS_TO_REQUIRED_STATS = {
    "Mage":     ["FlatMagicDamageMod"],
    "Assassin": ["FlatMagicDamageMod", "FlatPhysicalDamageMod"],
    "Marksman": ["FlatPhysicalDamageMod", "FlatCritChanceMod", "PercentAttackSpeedMod"],
    "Tank":     ["FlatHPPoolMod", "FlatArmorMod", "FlatSpellBlockMod"],
    "Fighter":  ["FlatPhysicalDamageMod", "FlatHPPoolMod"],
    "Support":  ["FlatHPPoolMod", "FlatArmorMod", "FlatSpellBlockMod"],
}
# tags to always exclude regardless of champion class
EXCLUDE_TAGS = {"Jungle", "Lane", "GoldPer", "Consumable", "Boots", "Vision", "Stealth"}


def get_champion_classes(champion_name: str) -> list:
    """Return the class tags for a champion e.g. ['Mage', 'Support']"""
    champ = champion_data.get(champion_name, {})
    return champ.get("tags", [])


def get_relevant_item_tags(champion_name: str) -> set:
    """Union all item tag sets for a champion's classes."""
    classes = get_champion_classes(champion_name)
    relevant = set()
    for cls in classes:
        relevant.update(CLASS_TO_ITEM_TAGS.get(cls, []))
    # fallback — if we couldn't map anything just return broad set
    if not relevant:
        relevant = {"Damage", "Health", "AbilityHaste", "SpellDamage"}
    return relevant


def filter_items_for_champion(champion_name: str, max_items: int = 25) -> dict:
    classes = get_champion_classes(champion_name)

    # union of required stats across all classes
    required_stats = set()
    for cls in classes:
        required_stats.update(CLASS_TO_REQUIRED_STATS.get(cls, []))

    if not required_stats:
        required_stats = {"FlatMagicDamageMod", "FlatPhysicalDamageMod"}

    filtered = {}
    for item_name, item in items_data.items():
        item_tags = set(item.get("tags", []))
        item_stats = set(item.get("stats", {}).keys())
        cost = item.get("cost", 0)

        # skip blacklisted, excluded tags, too cheap or absurdly expensive
        if item_name in ITEM_BLACKLIST:
            continue
        if item_tags & EXCLUDE_TAGS:
            continue
        if cost < 2500 or cost > 5000:  # only completed items in normal price range
            continue

        if item_stats & required_stats:
            filtered[item_name] = item

    sorted_items = sorted(filtered.items(), key=lambda x: x[1].get("cost", 0), reverse=True)
    return dict(sorted_items[:max_items])

def format_items_for_prompt(champion_name: str) -> str:
    """
    Return a formatted string of relevant items for a champion,
    ready to inject into the system prompt.
    """
    classes = get_champion_classes(champion_name)
    filtered = filter_items_for_champion(champion_name)

    if not filtered:
        return f"No item data available for {champion_name}."

    lines = [
        f"Current patch items relevant for {champion_name} ({', '.join(classes)}):",
    ]
    for item_name, item in filtered.items():
        stats_str = ", ".join(
            f"{k}: {v}" for k, v in item.get("stats", {}).items()
        ) or "no stats"
        lines.append(
            f"  - {item_name} ({item.get('cost', '?')}g) — {item.get('description', '')} | {stats_str}"
        )

    lines.append(
        f"\nBased on these items and the enemy composition, recommend the optimal build for {champion_name}."
    )
    return "\n".join(lines)


# -------------------------------------------------------
# Test
# -------------------------------------------------------
if __name__ == "__main__":
    for champ in ["Zoe", "Yasuo", "Leona", "Jinx", "Sylas"]:
        classes = get_champion_classes(champ)
        filtered = filter_items_for_champion(champ)
        print(f"{champ} ({classes}) — {len(filtered)} relevant items")

    print("\nSample prompt block for Zoe:")
    print(format_items_for_prompt("Zoe"))
