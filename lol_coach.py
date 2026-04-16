from groq import Groq
from dotenv import load_dotenv
import os
from pathlib import Path

# Load .env from the same directory as the script
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file")

client = Groq(api_key=api_key)


# --- fake user profile ---
user_profile = {
    "rank": "Gold",
    "role": "Mid",
    "playstyle": "aggressive",
    "favorite_champs": ["Yasuo","Zoe", "LeBlanc","Sylas"]
}

# --- fake game state ---
enemy_team = ["Malphite", "Lee Sin", "Ahri", "Jinx", "Leona"]

# --- SYSTEM PROMPT ---
system_prompt = f"""
You are a high-elo League of Legends coach. Given the enemy team composition and the user's profile, recommend the best champion pick and item build for the user.

User profile:
- Rank: {user_profile['rank']}
- Role: {user_profile['role']}
- Playstyle: {user_profile['playstyle']}
- Favorite champions to play: {user_profile['favorite_champs']}

IMPORTANT: 
- Only recommend champions from the user's favorite champions list: {user_profile['favorite_champs']}
- Do NOT recommend any other champions
- Do NOT recommend champions from the enemy team: {enemy_team}

Always respond with:
1. Best champion pick (MUST be from the favorite list)
2. Recommended item build 
3. Explanation (simple, actionable and in depth)
"""

# --- USER PROMPT ---
user_prompt = f"""
Enemy team composition: {enemy_team}

What should I pick and build?
"""

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
)

print(response.choices[0].message.content)