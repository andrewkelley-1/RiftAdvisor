import streamlit as st
from groq import Groq
from dotenv import load_dotenv
import os
import json
import sys
import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer

# add backend and prompts to path before importing from them
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR / "backend"))
sys.path.append(str(ROOT_DIR / "prompts"))

from riot_api import get_player_profile
from item_filter import format_items_for_prompt, get_champion_classes
from vector_store import retrieve_items
from prompt_builder import build_system_prompt

# -------------------------------------------------------
# Setup
# -------------------------------------------------------
load_dotenv(ROOT_DIR / ".env")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DATA_DIR = ROOT_DIR / "data"

def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

patch_info = load_json(DATA_DIR / "patch.json")
champion_data = load_json(DATA_DIR / "champions.json")

ALL_CHAMPIONS = [""] + sorted(champion_data.keys())
ROLES = ["Top", "Jungle", "Mid", "Bot", "Support"]
RANKS = ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Emerald", "Diamond", "Master", "Grandmaster", "Challenger"]

# -------------------------------------------------------
# Cache heavy resources so they load once per session
# -------------------------------------------------------
@st.cache_resource
def load_embedding_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

@st.cache_resource
def load_chroma_collection():
    c = chromadb.PersistentClient(path=str(ROOT_DIR / "chroma_db"))
    return c.get_collection("items")

# -------------------------------------------------------
# Page config
# -------------------------------------------------------
st.set_page_config(page_title="Rift Advisor", page_icon="⚔️", layout="wide")
st.title("⚔️ Rift Advisor")
st.caption(f"AI League of Legends Coach — Patch {patch_info['patch']}")

# -------------------------------------------------------
# Sidebar
# -------------------------------------------------------
with st.sidebar:
    st.header("Your Profile")

    riot_id_input = st.text_input("Riot ID", placeholder="Name#TAG")
    load_btn = st.button("Load Profile", use_container_width=True)

    if load_btn and riot_id_input:
        if "#" not in riot_id_input:
            st.error("Enter your full Riot ID with tag, e.g. saya#steez")
        else:
            with st.spinner("Fetching profile..."):
                try:
                    game_name, tag_line = riot_id_input.split("#", 1)
                    fetched = get_player_profile(game_name, tag_line)
                    st.session_state.fetched_profile = fetched

                    fetched_champs = fetched.get("favorite_champs", [])
                    for i in range(5):
                        champ = fetched_champs[i] if i < len(fetched_champs) else ""
                        st.session_state[f"fav{i}"] = champ if champ in champion_data else ""

                    if fetched.get("rank") in RANKS:
                        st.session_state["rank"] = fetched["rank"]
                    if fetched.get("role") in ROLES:
                        st.session_state["role"] = fetched["role"]

                    st.success(f"Loaded {fetched['rank_detail']} — {fetched['role']} main")
                except Exception as e:
                    st.error(f"Could not load profile: {e}")

    if "rank" not in st.session_state:
        st.session_state["rank"] = "Gold"
    if "role" not in st.session_state:
        st.session_state["role"] = "Mid"

    rank = st.selectbox("Rank", RANKS, key="rank")
    role = st.selectbox("Role", ROLES, key="role")

    st.markdown("**Favorite Champions** *(auto-filled from your account, or set manually)*")
    favs = []
    for i in range(5):
        favs.append(st.selectbox(f"Champion {i+1}", ALL_CHAMPIONS, key=f"fav{i}"))
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
# Session state init
# -------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_active" not in st.session_state:
    st.session_state.session_active = False

if start:
    fetched = st.session_state.get("fetched_profile", {})
    profile = {
        "riot_id": f"{fetched.get('game_name', '')}#{fetched.get('tag_line', '')}" if fetched else "",
        "rank": rank,
        "role": role,
        "favorite_champs": favorite_champs,
        "recent_matches": fetched.get("recent_matches", []),
    }

    model = load_embedding_model()
    collection = load_chroma_collection()

    system_prompt = build_system_prompt(
        profile,
        ally_team,
        enemy_team,
        patch=patch_info["patch"],
        model=model,
        collection=collection,
    )

    st.session_state.messages = [{"role": "system", "content": system_prompt}]
    st.session_state.session_active = True
    st.session_state.profile = profile
    st.session_state.ally_team = ally_team
    st.session_state.enemy_team = enemy_team

    # auto-send opening question
    opening = "Based on my profile and the current draft, what champion should I pick and what should I build?"
    st.session_state.messages.append({"role": "user", "content": opening})
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=st.session_state.messages
    )
    reply = response.choices[0].message.content
    st.session_state.messages.append({"role": "assistant", "content": reply})

# -------------------------------------------------------
# Main chat area
# -------------------------------------------------------
if not st.session_state.session_active:
    st.info("Load your profile or fill it in manually, set the draft in the sidebar, then click **Start Session**.")
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

    recent = profile.get("recent_matches", [])
    if recent:
        with st.expander(f"Recent Match History ({len(recent)} games)"):
            wins = sum(1 for m in recent if m["win"])
            st.caption(f"Record: {wins}W {len(recent) - wins}L")
            for m in recent:
                result_color = "🟢" if m["win"] else "🔴"
                kda = f"{m['kills']}/{m['deaths']}/{m['assists']}"
                st.markdown(f"{result_color} **{m['champion']}** ({m['role']}) — {kda}")

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