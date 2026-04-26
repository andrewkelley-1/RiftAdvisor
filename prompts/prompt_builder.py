import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR / "backend"))

from item_filter import get_champion_classes
from vector_store import retrieve_items


def format_team(team_dict: dict) -> str:
    return "\n".join(
        f"  - {role}: {champ}" for role, champ in team_dict.items() if champ
    ) or "  None selected"


def format_match_history(matches: list) -> str:
    if not matches:
        return "  No recent match data available."
    lines = []
    for m in matches:
        result = "WIN" if m["win"] else "LOSS"
        kda = f"{m['kills']}/{m['deaths']}/{m['assists']}"
        lines.append(f"  - {m['champion']} ({m['role']}) — {result} {kda}")
    wins = sum(1 for m in matches if m["win"])
    lines.append(f"  Recent record: {wins}W {len(matches) - wins}L")
    return "\n".join(lines)


def build_system_prompt(
    profile: dict,
    ally_team: dict,
    enemy_team: dict,
    patch: str,
    model=None,
    collection=None,
) -> str:
    """
    Dynamically constructs the full system prompt by combining:
    - User profile (rank, role, favorite champions)
    - Recent match history from Riot API
    - Full draft state (ally and enemy teams by role)
    - Semantically retrieved item data from Chroma vector store (RAG)

    Design decisions:
    - System prompt explicitly references user rank and role to personalize tone and depth
    - Match history is injected so the coach can reference recent performance in tips
    - Two separate RAG queries are made: one offensive (what to build for damage)
      and one defensive (what to build against this enemy comp) for broader coverage
    - Champion restriction is conditionally applied based on whether favorites are set
    """

    enemy_champs = [c for c in enemy_team.values() if c]

    # --- champion restriction ---
    if profile["favorite_champs"]:
        champ_restriction = (
            f"Only recommend champions from the user's favorite list: {profile['favorite_champs']}"
        )
        first_champ = profile["favorite_champs"][0]
        classes = get_champion_classes(first_champ)
        role_class = ", ".join(classes).lower() if classes else "champion"
    else:
        champ_restriction = (
            "The user has no favorite champions — recommend the single best champion "
            "for this situation from the entire champion pool."
        )
        role_class = profile["role"].lower()

    # --- RAG: semantic item retrieval ---
    # two queries: one for offensive items, one for defensive/situational
    if enemy_champs:
        offensive_query = (
            f"{role_class} champion in {profile['role']} lane against {', '.join(enemy_champs)}"
        )
        defensive_query = (
            f"survivability and defensive items against {', '.join(enemy_champs)}"
        )
    else:
        offensive_query = f"best items for {role_class} in {profile['role']} lane"
        defensive_query = f"defensive items for {role_class}"

    offensive_items = retrieve_items(offensive_query, n_results=10, model=model, collection=collection)
    defensive_items = retrieve_items(defensive_query, n_results=8, model=model, collection=collection)

    build_section = f"""--- RETRIEVED ITEM DATA (semantic search, Patch {patch}) ---
Offensive / core items:
{offensive_items}

Defensive / situational items:
{defensive_items}
--- END ITEM DATA ---"""

    # --- match history ---
    match_section = format_match_history(profile.get("recent_matches", []))

    return f"""
You are a high-elo League of Legends coach. Given the full draft and the user's profile, recommend the best champion pick and item build.

User profile:
- Riot ID: {profile.get('riot_id', 'Unknown')}
- Rank: {profile['rank']}
- Role: {profile['role']}
- Favorite champions: {profile['favorite_champs'] if profile['favorite_champs'] else 'None — recommend from full champion pool'}

Recent match history:
{match_section}

Allied team (by role):
{format_team(ally_team)}

Enemy team (by role):
{format_team(enemy_team)}

IMPORTANT:
- {champ_restriction}
- Do NOT recommend champions already picked by allies or enemies
- Consider both ally synergies and enemy counters when making your recommendation
- Base item recommendations ONLY on the retrieved item data provided below
- Take the user's recent match history into account when giving gameplay tips

{build_section}

Always respond with:
1. Best champion pick, why it counters the enemy comp, and how it synergizes with allies
2. Recommended item build with explanation of each item choice
3. One or two gameplay tips based on their recent performance and this matchup
"""
