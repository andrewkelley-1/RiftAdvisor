from groq import Groq
from dotenv import load_dotenv
import os
import json
from pathlib import Path

# -------------------------------------------------------
# Setup
# -------------------------------------------------------
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file")

client = Groq(api_key=api_key)

DATA_DIR = Path(__file__).parent / "data"
BUILDS_DIR = Path(__file__).parent / "builds"

# -------------------------------------------------------
# Load Data Dragon cache + curated builds
# -------------------------------------------------------
def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

# make sure data exists
if not (DATA_DIR / "items.json").exists():
    raise FileNotFoundError("data/items.json not found. Run data_dragon.py first.")
if not (BUILDS_DIR / "champion_builds.json").exists():
    raise FileNotFoundError("builds/champion_builds.json not found. Create it first.")

items_data = load_json(DATA_DIR / "items.json")
champion_builds = load_json(BUILDS_DIR / "champion_builds.json")
patch_info = load_json(DATA_DIR / "patch.json")


# -------------------------------------------------------
# Build enrichment — injects real item stats into prompt
# -------------------------------------------------------
def get_item_stats(item_name: str) -> str:
    item = items_data.get(item_name)
    if not item:
        return f"{item_name}: (data not found)"
    stats_str = ", ".join(f"{k}: {v}" for k, v in item["stats"].items()) or "no stats"
    return f"{item_name} ({item['cost']}g) — {item['description']} | Stats: {stats_str}"


def enrich_build(build: list) -> str:
    return "\n".join(f"  - {get_item_stats(item)}" for item in build)


def get_build_context(champion: str, role: str) -> str:
    """
    Look up the curated build for a champion/role combo and enrich it
    with real item stats from Data Dragon. Returns a formatted string
    ready to inject into the system prompt.
    """
    champ_data = champion_builds.get(champion)
    if not champ_data:
        return f"No curated build found for {champion}."

    role_data = champ_data.get(role) or champ_data.get(list(champ_data.keys())[0])

    core = role_data.get("core_items", [])
    situational = role_data.get("situational", [])
    boots = role_data.get("boots", "")

    context = f"Patch {patch_info['patch']} recommended build for {champion} ({role}):\n"
    context += f"\nCore items:\n{enrich_build(core)}"
    context += f"\n\nSituational items:\n{enrich_build(situational)}"
    if boots:
        context += f"\n\nBoots:\n{enrich_build([boots])}"

    return context


# -------------------------------------------------------
# User profile + game state
# -------------------------------------------------------
user_profile = {
    "rank": "Gold",
    "role": "Mid",
    "playstyle": "aggressive",
    "favorite_champs": ["Zoe", "LeBlanc", "Sylas"]
}

enemy_team = ["Malphite", "Lee Sin", "Ahri", "Jinx", "Leona"]

# -------------------------------------------------------
# Build system prompt with enriched item context injected
# -------------------------------------------------------
# pre-load build context for all favorite champs so the
# model has full item data for any pick it might recommend
build_context_block = ""
for champ in user_profile["favorite_champs"]:
    build_context_block += get_build_context(champ, user_profile["role"]) + "\n\n"

system_prompt = f"""
You are a high-elo League of Legends coach. Given the enemy team composition and the user's profile, recommend the best champion pick and item build for the user.

User profile:
- Rank: {user_profile['rank']}
- Role: {user_profile['role']}
- Playstyle: {user_profile['playstyle']}
- Favorite champions: {user_profile['favorite_champs']}

Current enemy team: {enemy_team}

IMPORTANT:
- Only recommend champions from the user's favorite champions list
- Do NOT recommend champions from the enemy team
- Base your item recommendations ONLY on the verified build data below — do not invent items

--- VERIFIED BUILD DATA (current patch, sourced from U.GG) ---
{build_context_block}
--- END BUILD DATA ---

Always respond with:
1. Best champion pick and why it counters this enemy comp
2. Recommended item build with explanation of each item choice
3. One or two gameplay tips for this matchup

For follow-up questions, maintain context of your previous recommendations.
"""

# -------------------------------------------------------
# Conversation loop
# -------------------------------------------------------
messages = [{"role": "system", "content": system_prompt}]

print(f"LoL AI Coach (Patch {patch_info['patch']}) — type 'quit' to exit\n")
print(f"Enemy team: {enemy_team}")
print(f"Your champs: {user_profile['favorite_champs']}\n")

while True:
    user_input = input("You: ").strip()

    if user_input.lower() in ["quit", "exit", "q"]:
        print("Good luck on the rift!")
        break

    if not user_input:
        continue

    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )

    reply = response.choices[0].message.content
    messages.append({"role": "assistant", "content": reply})

    print(f"\nCoach: {reply}\n")