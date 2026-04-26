import json
import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).parent / "data"
CHROMA_DIR = Path(__file__).parent / "chroma_db"

def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

# -------------------------------------------------------
# Strategic context for key items
# Teaches the embedding model WHEN and WHY to buy each item
# -------------------------------------------------------
STRATEGIC_CONTEXT = {
    # defensive AP items
    "Banshee's Veil": "Best against heavy AP teams and champions with dangerous single target abilities or crowd control. Buy when the enemy has a lot of magic damage, AP assassins, or hard CC like Malphite, Galio, Syndra, or Zoe.",
    "Zhonya's Hourglass": "Best against AD assassins and burst damage. Use the active to dodge ultimates like Zed, Karthus, or Fizz. Also good against heavy engage compositions.",
    "Shadowflame": "Best against squishy targets and teams with shields. Penetrates magic shields. Strong first or second item for burst mages like LeBlanc or Lux.",
    "Void Staff": "Buy when enemies are building magic resistance. Essential for mages in mid or late game against tanky enemies. Provides magic penetration.",
    "Rabadon's Deathcap": "Core mage item for maximum ability power. Buy as third or fourth item when ahead. Amplifies all existing AP.",
    "Luden's Echo": "Strong early mage item for poke and wave clear. Good on champions like Lux, Xerath, or Zoe who want to poke from range.",
    "Morellonomicon": "Buy against healing heavy enemies or tanks with regeneration. Applies Grievous Wounds to reduce healing.",
    "Liandry's Torment": "Best against tanks and high health enemies. Deals percentage health damage over time. Strong on Malzahar, Teemo, or Brand.",
    "Cosmic Drive": "Good on mages who want ability haste and survivability. Provides health and movement speed for mobile mage playstyles.",
    "Cryptbloom": "Buy against teams with heavy magic damage to get magic resistance while still dealing AP damage.",
    "Archangel's Staff": "Best on mana-hungry mages like Ryze, Cassiopeia, or Anivia who cast spells constantly. Converts mana into ability power.",
    "Lich Bane": "Buy on mages who auto attack between spells like Twisted Fate, Ekko, or Lux. Empowers next attack after casting a spell.",
    "Blackfire Torch": "Good on AOE mages who hit multiple enemies. Deals bonus magic damage on AOE abilities.",
    "Bloodletter's Curse": "Buy on AP champions when you want to help your team deal more magic damage. Reduces enemy magic resistance on hit.",

    # marksman items
    "Infinity Edge": "Core critical strike item for marksmen. Buy after two crit items to maximize critical strike damage. Essential on Jinx, Caitlyn, Jhin.",
    "Kraken Slayer": "Best marksman item against tanks. Every third hit deals true damage, shredding through armor and health. Buy against Malphite, Ornn, or Cho'Gath.",
    "Immortal Shieldbow": "Defensive marksman item that grants a shield when low health. Buy when you need survivability against assassins or burst damage.",
    "Lord Dominik's Regards": "Buy against tanks and enemies stacking armor. Provides armor penetration and bonus damage against high health targets.",
    "Mortal Reminder": "Buy against healing heavy enemies. Applies Grievous Wounds to reduce healing. Good against Soraka, Vladimir, or Aatrox.",
    "Galeforce": "Mobile marksman item that grants a dash. Good on champions who want mobility like Xayah or Kai'Sa.",
    "Runaan's Hurricane": "Buy on marksmen who benefit from hitting multiple targets. Fires bolts at nearby enemies. Great on Jinx, Twitch, or Kog'Maw.",
    "Guinsoo's Rageblade": "Buy on on-hit marksmen who attack fast. Converts critical strike into on-hit damage. Best on Kog'Maw, Jinx, or Kaisa.",

    # tank items
    "Warmog's Armor": "Buy when you need maximum health and sustain. Best on tanks with health scaling like Cho'Gath or Zac.",
    "Thornmail": "Buy against heavy attack damage and healing. Reflects damage and applies Grievous Wounds. Best against fed ADCs or healing champions.",
    "Gargoyle Stoneplate": "Best tank item against mixed damage teams with both AP and AD. Active doubles bonus health temporarily.",
    "Sunfire Aegis": "Good on engage tanks who stay in melee range. Deals damage to nearby enemies over time.",
    "Heartsteel": "Stack health by hitting enemy champions. Best on high health tanks like Cho'Gath or Sion who scale with health.",
    "Frozen Heart": "Buy against attack speed heavy teams or marksmen. Reduces nearby enemy attack speed.",
    "Randuin's Omen": "Buy against critical strike heavy teams. Reduces damage from critical strikes and slows nearby enemies on activation.",

    # fighter items
    "Trinity Force": "Best on fighters and juggernauts who auto attack frequently between abilities. Good on Nasus, Irelia, or Camille.",
    "Black Cleaver": "Buy on AD fighters against tanks. Stacks armor reduction on hit and provides health and ability haste.",
    "Death's Dance": "Defensive AD item that delays damage as a bleed. Best against burst assassins. Good on Fiora, Darius, or Aatrox.",
    "Sterak's Gage": "Buy against burst damage. Grants a massive shield when low health. Best on tanky fighters like Darius or Garen.",
    "Ravenous Hydra": "Buy on melee fighters for wave clear and healing. Provides life steal and AOE damage on attacks.",
    "Spear of Shojin": "Buy on fighters who use lots of abilities rapidly. Reduces cooldowns based on ability usage.",

    # support items
    "Redemption": "Buy on supports who want to heal their team in fights. Active heals nearby allies. Good on Soraka, Lulu, or Janna.",
    "Mikael's Blessing": "Buy against heavy crowd control to cleanse allies. Active removes crowd control from an ally.",
    "Shurelya's Battlesong": "Buy on engage or roaming supports who want to speed up their team. Active grants movement speed to nearby allies.",
    "Locket of the Iron Solari": "Buy against heavy AP burst. Active shields nearby allies against magic damage. Essential against Orianna or Syndra.",

    # situational
    "Serpent's Fang": "Buy against shield heavy teams. Reduces effectiveness of shields on enemies you damage.",
    "Chempunk Chainsword": "AD Grievous Wounds item. Buy against healing heavy enemies when playing AD champions.",
    "Maw of Malmortius": "Buy on AD champions against heavy AP. Grants a magic damage absorbing shield when low health.",
    "Edge of Night": "Buy on AD assassins against poke or single target CC. Grants a spell shield.",
    "Wit's End": "Buy on AD or AP fighters against heavy magic damage teams. Provides magic resistance and attack speed.",
}

# -------------------------------------------------------
# Build a human-readable document for each item
# -------------------------------------------------------
def item_to_document(item_name: str, item: dict) -> str:
    stats = item.get("stats", {})
    description = item.get("description", "")
    cost = item.get("cost", 0)
    tags = item.get("tags", [])

    stat_map = {
        "FlatMagicDamageMod": "ability power",
        "FlatPhysicalDamageMod": "attack damage",
        "FlatHPPoolMod": "health",
        "FlatArmorMod": "armor",
        "FlatSpellBlockMod": "magic resistance",
        "FlatCritChanceMod": "critical strike chance",
        "PercentAttackSpeedMod": "attack speed",
        "FlatMPPoolMod": "mana",
        "PercentLifeStealMod": "life steal",
        "PercentMovementSpeedMod": "movement speed",
    }

    stat_lines = []
    for stat_key, stat_label in stat_map.items():
        if stat_key in stats:
            val = stats[stat_key]
            if isinstance(val, float) and val < 1:
                stat_lines.append(f"{int(val * 100)}% {stat_label}")
            else:
                stat_lines.append(f"{val} {stat_label}")

    doc = f"{item_name} costs {cost} gold."
    if description:
        doc += f" {description}."
    if stat_lines:
        doc += f" Provides {', '.join(stat_lines)}."
    if tags:
        doc += f" Item tags: {', '.join(tags)}."
    if item_name in STRATEGIC_CONTEXT:
        doc += f" Strategic use: {STRATEGIC_CONTEXT[item_name]}"

    return doc


# -------------------------------------------------------
# Build and persist the Chroma vector store
# -------------------------------------------------------
def build_vector_store():
    print("Loading item data...")
    items_data = load_json(DATA_DIR / "items.json")

    BLACKLIST = {
        "The Golden Spatula", "Wooglet's Witchcap",
        "Deathfire Grasp", "Void Immolation"
    }

    completed_items = {
        name: item for name, item in items_data.items()
        if name not in BLACKLIST
        and item.get("cost", 0) >= 2500
        and item.get("cost", 0) <= 5000
        and not ({"Jungle", "Lane", "Consumable", "Boots"} & set(item.get("tags", [])))
    }

    print(f"Indexing {len(completed_items)} items...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    documents = []
    embeddings = []
    ids = []
    metadatas = []

    for item_name, item in completed_items.items():
        doc = item_to_document(item_name, item)
        embedding = model.encode(doc).tolist()
        documents.append(doc)
        embeddings.append(embedding)
        ids.append(item_name)
        metadatas.append({
            "name": item_name,
            "cost": item.get("cost", 0),
            "tags": ",".join(item.get("tags", [])),
        })

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection("items")
    except Exception:
        pass

    collection = client.create_collection("items")
    collection.add(
        documents=documents,
        embeddings=embeddings,
        ids=ids,
        metadatas=metadatas,
    )

    print(f"Vector store built and saved to {CHROMA_DIR}/")
    return collection


# -------------------------------------------------------
# Query the vector store
# -------------------------------------------------------
def retrieve_items(query: str, n_results: int = 15) -> str:
    """
    Given a natural language query describing the game situation,
    retrieve the most semantically relevant items and return them
    as a formatted string ready to inject into the prompt.
    """
    model = SentenceTransformer("all-MiniLM-L6-v2")
    query_embedding = model.encode(query).tolist()

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection("items")

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
    )

    ids = results["ids"][0]
    docs = results["documents"][0]

    lines = [f"Semantically retrieved items relevant to: '{query}'\n"]
    for item_name, doc in zip(ids, docs):
        lines.append(f"  - {doc}")

    return "\n".join(lines)


# -------------------------------------------------------
# Test
# -------------------------------------------------------
if __name__ == "__main__":
    build_vector_store()

    print("\n--- Test Query 1: heavy AP engage ---")
    print(retrieve_items("mid lane mage against heavy AP engage with Malphite and Galio", n_results=5))

    print("\n--- Test Query 2: marksman against armor stackers ---")
    print(retrieve_items("marksman bot lane against tanks and armor stackers", n_results=5))

    print("\n--- Test Query 3: need survivability against burst ---")
    print(retrieve_items("need a shield or damage blocking item to survive burst damage", n_results=5))