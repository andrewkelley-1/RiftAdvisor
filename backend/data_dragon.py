import requests
import json
from pathlib import Path

# -------------------------------------------------------
# Data Dragon fetcher
# Pulls the latest patch item + champion data and saves
# -------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def get_latest_patch():
    url = "https://ddragon.leagueoflegends.com/api/versions.json"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()[0]


def fetch_items(patch: str) -> dict:
    url = f"https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/item.json"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()["data"]


def fetch_champions(patch: str) -> dict:
    url = f"https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/champion.json"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()["data"]


def parse_items(raw_items: dict) -> dict:
    """
    Strip down the raw item data to just what's useful for prompt injection.
    Filters out jungle items, consumables, and component-only items.
    """
    parsed = {}
    for item_id, item in raw_items.items():
        # skip components, consumables, and items not available in the store
        if not item.get("inStore", True):
            continue
        if item.get("consumed"):
            continue

        stats = item.get("stats", {})
        tags = item.get("tags", [])
        gold = item.get("gold", {})
        total_cost = gold.get("total", 0)

        # only include items that cost 1000g+ (completed items, not components)
        if total_cost < 1000:
            continue

        parsed[item["name"]] = {
            "id": item_id,
            "cost": total_cost,
            "stats": stats,
            "tags": tags,
            "description": item.get("plaintext", ""),
        }

    return parsed


def parse_champions(raw_champs: dict) -> dict:
    """
    Strip down champion data to key info for prompt injection.
    """
    parsed = {}
    for champ_id, champ in raw_champs.items():
        parsed[champ["name"]] = {
            "id": champ_id,
            "key": champ["key"],          # add this line
            "title": champ.get("title", ""),
            "tags": champ.get("tags", []),
            "stats": champ.get("stats", {}),
            "partype": champ.get("partype", "Mana"),
        }
    return parsed


def save_json(data: dict, filepath: Path):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(data)} entries to {filepath}")


def load_json(filepath: Path) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_item_stats(item_name: str, items_data: dict) -> str:
    """
    Given an item name, return a formatted string of its stats
    for prompt injection. Used by the coach to enrich build recommendations.
    """
    item = items_data.get(item_name)
    if not item:
        return f"{item_name}: (data not found)"

    stats_str = ", ".join(
        f"{k}: {v}" for k, v in item["stats"].items()
    ) or "no stats"

    return (
        f"{item_name} ({item['cost']}g) — {item['description']} | Stats: {stats_str}"
    )


def enrich_build(build: list[str], items_data: dict) -> str:
    """
    Take a list of item names and return a formatted block
    ready to inject into a system prompt.
    """
    lines = []
    for item_name in build:
        lines.append(f"  - {get_item_stats(item_name, items_data)}")
    return "\n".join(lines)


# -------------------------------------------------------
# Main — run this once to download and cache the data
# -------------------------------------------------------
if __name__ == "__main__":
    print("Fetching latest patch version...")
    patch = get_latest_patch()
    print(f"Current patch: {patch}")

    print("Fetching item data...")
    raw_items = fetch_items(patch)
    items = parse_items(raw_items)
    save_json(items, DATA_DIR / "items.json")

    print("Fetching champion data...")
    raw_champs = fetch_champions(patch)
    champions = parse_champions(raw_champs)
    save_json(champions, DATA_DIR / "champions.json")

    # save the patch version so we know when to refresh
    save_json({"patch": patch}, DATA_DIR / "patch.json")

    print(f"\nDone. Data saved to {DATA_DIR}/")
    print("Run this script again at the start of each new patch to refresh.")

    # quick sanity check
    print("\nSample item lookup:")
    print(get_item_stats("Infinity Edge", items))

    print("\nSample champion lookup:")
    yasuo = champions.get("Yasuo", {})
    print(f"Yasuo — {yasuo.get('title')} | Tags: {yasuo.get('tags')} | Resource: {yasuo.get('partype')}")
