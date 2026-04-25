import streamlit as st
from groq import Groq
from dotenv import load_dotenv
import os
import json
from pathlib import Path

# -------------------------------------------------------
# Setup
# -------------------------------------------------------
load_dotenv(Path(__file__).parent / '.env')
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DATA_DIR = Path(__file__).parent / "data"
BUILDS_DIR = Path(__file__).parent / "builds"

def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

items_data = load_json(DATA_DIR / "items.json")
champion_builds = load_json(BUILDS_DIR / "champion_builds.json")
patch_info = load_json(DATA_DIR / "patch.json")
champion_data = load_json(DATA_DIR / "champions.json")

ALL_CHAMPIONS = [""] + sorted(champion_data.keys())
ROLES = ["Top", "Jungle", "Mid", "Bot", "Support"]

# -------------------------------------------------------
# Build enrichment
# -------------------------------------------------------
def get_item_stats(item_name):
    item = items_data.get(item_name)
    if not item:
        return f"{item_name}: (data not found)"
    stats_str = ", ".join(f"{k}: {v}" for k, v in item["stats"].items()) or "no stats"
    return f"{item_name} ({item['cost']}g) — {item['description']} | Stats: {stats_str}"

def enrich_build(build):
    return "\n".join(f"  - {get_item_stats(item)}" for item in build)

def get_build_context(champion, role):
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

def format_team(team_dict):
    return "\n".join(
        f"  - {role}: {champ}" for role, champ in team_dict.items() if champ
    ) or "  None selected"

def build_system_prompt(profile, ally_team, enemy_team):
    # handle optional favorites
    if profile["favorite_champs"]:
        champ_restriction = f"Only recommend champions from the user's favorite list: {profile['favorite_champs']}"
        build_context_block = ""
        for champ in profile["favorite_champs"]:
            build_context_block += get_build_context(champ, profile["role"]) + "\n\n"
        build_section = f"""--- VERIFIED BUILD DATA (Patch {patch_info['patch']}, sourced from U.GG) ---
{build_context_block}
--- END BUILD DATA ---"""
    else:
        champ_restriction = "The user has no favorite champions — recommend the single best champion for this situation from the entire champion pool."
        build_section = "No curated builds provided. Use your knowledge to recommend a strong current-meta build for whatever champion you recommend."

    return f"""
You are a high-elo League of Legends coach. Given the full draft and the user's profile, recommend the best champion pick and item build.

User profile:
- Rank: {profile['rank']}
- Role: {profile['role']}
- Playstyle: {profile['playstyle']}
- Favorite champions: {profile['favorite_champs'] if profile['favorite_champs'] else 'None — recommend from full champion pool'}

Allied team (by role):
{format_team(ally_team)}

Enemy team (by role):
{format_team(enemy_team)}

IMPORTANT:
- {champ_restriction}
- Do NOT recommend champions already picked by allies or enemies
- Consider both ally synergies and enemy counters when making your recommendation

{build_section}

Always respond with:
1. Best champion pick, why it counters the enemy comp, and how it synergizes with allies
2. Recommended item build with explanation of each item choice
3. One or two gameplay tips for this matchup
"""

# -------------------------------------------------------
# Page config
# -------------------------------------------------------
st.set_page_config(page_title="Rift Advisor", page_icon="⚔️", layout="wide")
st.title("⚔️ Rift Advisor")
st.caption(f"AI League of Legends Coach — Patch {patch_info['patch']}")

# -------------------------------------------------------
# Sidebar — user profile
# -------------------------------------------------------
with st.sidebar:
    st.header("Your Profile")

    rank = st.selectbox("Rank", [
        "Iron", "Bronze", "Silver", "Gold", "Platinum",
        "Emerald", "Diamond", "Master", "Grandmaster", "Challenger"
    ], index=3)

    role = st.selectbox("Role", ROLES, index=2)
    playstyle = st.selectbox("Playstyle", ["Aggressive", "Passive", "Balanced", "Roaming"])

    st.markdown("**Favorite Champions** *(optional — leave blank for best overall pick)*")
    favs = [st.selectbox(f"Champion {i+1}", ALL_CHAMPIONS, key=f"fav{i}") for i in range(5)]
    favorite_champs = [c for c in favs if c]

    st.divider()

    st.header("Your Team")
    ally_team = {}
    for r in ROLES:
        label = f"{r} (You)" if r == role else r
        ally_team[r] = st.selectbox(label, ALL_CHAMPIONS, key=f"ally_{r}")

    st.divider()

    st.header("Enemy Team")
    enemy_team = {}
    for r in ROLES:
        enemy_team[r] = st.selectbox(r, ALL_CHAMPIONS, key=f"enemy_{r}")

    start = st.button("Start Session", type="primary", use_container_width=True)

# -------------------------------------------------------
# Session state
# -------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_active" not in st.session_state:
    st.session_state.session_active = False

if start:
    profile = {
        "rank": rank,
        "role": role,
        "playstyle": playstyle.lower(),
        "favorite_champs": favorite_champs
    }
    system_prompt = build_system_prompt(profile, ally_team, enemy_team)
    st.session_state.messages = [{"role": "system", "content": system_prompt}]
    st.session_state.session_active = True
    st.session_state.profile = profile
    st.session_state.ally_team = ally_team
    st.session_state.enemy_team = enemy_team

# -------------------------------------------------------
# Main chat area
# -------------------------------------------------------
if not st.session_state.session_active:
    st.info("Fill out your profile and draft in the sidebar, then click **Start Session**.")
else:
    profile = st.session_state.profile
    ally_team = st.session_state.ally_team
    enemy_team = st.session_state.enemy_team

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Your Team**")
        for r, c in ally_team.items():
            if c:
                label = f"**{r} (You)**" if r == profile["role"] else r
                st.markdown(f"- {label}: {c}")
    with col2:
        st.markdown("**Enemy Team**")
        for r, c in enemy_team.items():
            if c:
                st.markdown(f"- {r}: {c}")

    st.divider()

    for msg in st.session_state.messages[1:]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask your coach...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=st.session_state.messages
                )
                reply = response.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": reply})
                st.markdown(reply)