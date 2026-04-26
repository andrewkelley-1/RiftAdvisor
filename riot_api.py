import requests
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / '.env')

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
if not RIOT_API_KEY:
    raise ValueError("RIOT_API_KEY not found in .env file")

# -------------------------------------------------------
# Region config
# Americas covers NA, Brazil, Latin America
# -------------------------------------------------------
PLATFORM = "na1"            # server (na1, euw1, kr, etc.)
REGION = "americas"         # regional cluster for match/account endpoints

HEADERS = {"X-Riot-Token": RIOT_API_KEY}

# -------------------------------------------------------
# Core API calls
# -------------------------------------------------------
def get_account_by_riot_id(game_name: str, tag_line: str) -> dict:
    """
    Fetch PUUID from Riot ID (e.g. game_name='Faker', tag_line='T1').
    This is the new standard — summoner names are being deprecated.
    """
    url = f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def get_rank(puuid: str) -> dict:
    url = f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    """
    Fetch ranked stats for a summoner.
    Returns tier (GOLD, PLATINUM etc.) and rank (I, II, III, IV).
    """
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    entries = response.json()

    # find solo queue rank specifically
    for entry in entries:
        if entry.get("queueType") == "RANKED_SOLO_5x5":
            return {
                "tier": entry["tier"].capitalize(),   # e.g. "Gold"
                "rank": entry["rank"],                 # e.g. "II"
                "lp": entry["leaguePoints"],
                "wins": entry["wins"],
                "losses": entry["losses"]
            }

    return {"tier": "Unranked", "rank": "", "lp": 0, "wins": 0, "losses": 0}


def get_top_champions(puuid: str, count: int = 5) -> list[str]:
    """
    Fetch top N champions by mastery points.
    Returns a list of champion names (strings).
    """
    url = f"https://{PLATFORM}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?count={count}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    masteries = response.json()

    # map champion IDs to names using the static data we already have
    from data_dragon import load_json
    from pathlib import Path
    champion_data = load_json(Path(__file__).parent / "data" / "champions.json")

    # build reverse map: champion numeric ID -> name
    id_to_name = {str(int(data["key"])): name for name, data in champion_data.items()}

    return [
        id_to_name.get(str(m["championId"]), f"Unknown({m['championId']})")
        for m in masteries
    ]


def get_recent_matches(puuid: str, count: int = 10) -> list[str]:
    """Fetch list of recent match IDs."""
    url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count={count}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def get_match_detail(match_id: str, puuid: str) -> dict:
    """
    Fetch a single match and extract stats for our player.
    Returns champion played, role, result, and KDA.
    """
    url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    match = response.json()

    # find our player's participant data
    for participant in match["info"]["participants"]:
        if participant["puuid"] == puuid:
            return {
                "champion": participant["championName"],
                "role": participant.get("teamPosition", "UNKNOWN"),
                "win": participant["win"],
                "kills": participant["kills"],
                "deaths": participant["deaths"],
                "assists": participant["assists"],
            }
    return {}


def get_match_history_summary(puuid: str, count: int = 10) -> list[dict]:
    """Fetch and parse the last N matches for a player."""
    match_ids = get_recent_matches(puuid, count)
    summary = []
    for match_id in match_ids:
        detail = get_match_detail(match_id, puuid)
        if detail:
            summary.append(detail)
    return summary


# -------------------------------------------------------
# Main profile builder — call this from app.py
# -------------------------------------------------------
def get_player_profile(game_name: str, tag_line: str) -> dict:
    """
    Given a Riot ID (game name + tag), fetch and return a full
    player profile ready to inject into the system prompt.
    """
    print(f"Fetching profile for {game_name}#{tag_line}...")

    account = get_account_by_riot_id(game_name, tag_line)
    puuid = account["puuid"]
    print("PUUID:", puuid)

    rank_info = get_rank(puuid)
    top_champs = get_top_champions(puuid, count=5)
    match_history = get_match_history_summary(puuid, count=10)

    # figure out most played role from recent matches
    role_counts = {}
    for match in match_history:
        r = match.get("role", "UNKNOWN")
        role_counts[r] = role_counts.get(r, 0) + 1
    most_played_role = max(role_counts, key=role_counts.get) if role_counts else "UNKNOWN"

    # map Riot's role names to readable ones
    role_map = {
        "TOP": "Top", "JUNGLE": "Jungle", "MIDDLE": "Mid",
        "BOTTOM": "Bot", "UTILITY": "Support", "UNKNOWN": "Unknown"
    }

    return {
        "game_name": game_name,
        "tag_line": tag_line,
        "puuid": puuid,
        "rank": rank_info["tier"],
        "rank_detail": f"{rank_info['tier']} {rank_info['rank']} {rank_info['lp']}LP",
        "wins": rank_info["wins"],
        "losses": rank_info["losses"],
        "role": role_map.get(most_played_role, most_played_role),
        "favorite_champs": top_champs,
        "recent_matches": match_history,
    }


# -------------------------------------------------------
# Test — run this file directly to verify your API key
# -------------------------------------------------------
if __name__ == "__main__":
    # replace with your own Riot ID to test
    game_name = "saya"
    tag_line = "steez"

    try:
        profile = get_player_profile(game_name, tag_line)
        print("\n--- Player Profile ---")
        print(f"Name:      {profile['game_name']}#{profile['tag_line']}")
        print(f"Rank:      {profile['rank_detail']}")
        print(f"W/L:       {profile['wins']}W {profile['losses']}L")
        print(f"Main role: {profile['role']}")
        print(f"Top champs: {profile['favorite_champs']}")
        print(f"\nRecent matches ({len(profile['recent_matches'])}):")
        for m in profile["recent_matches"]:
            result = "WIN" if m["win"] else "LOSS"
            print(f"  {m['champion']} ({m['role']}) — {result} — {m['kills']}/{m['deaths']}/{m['assists']}")
    except Exception as e:
        print(f"Error: {e}")
