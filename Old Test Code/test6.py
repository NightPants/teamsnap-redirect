import requests
import webbrowser
from urllib.parse import urlencode
from datetime import datetime

# Credentials and URLs
CLIENT_ID = "Eocrv5rmAg8v33ADCmM0dFS8dE4Vw6UJ5RdtIRDPojk"
CLIENT_SECRET = "xtIrH7i_doYM4Jj-jVlDXiBjCkqTT1wMmbHQa9tzGuM"
AUTH_URL = "https://auth.teamsnap.com/oauth/authorize"
TOKEN_URL = "https://auth.teamsnap.com/oauth/token"
REDIRECT_URI = "https://github.com/NightPants/teamsnap-redirect"
USER_INFO_URL = "https://api.teamsnap.com/v3/me"
TEAMS_URL = "https://api.teamsnap.com/v3/teams"
EVENTS_URL = "https://api.teamsnap.com/v3/events/search"

# Step 1: Generate Authorization URL
def get_authorization_url():
    auth_params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "read write",
    }
    return f"{AUTH_URL}?{urlencode(auth_params)}"

# Step 2: Get Authorization Code
def get_authorization_code():
    auth_url = get_authorization_url()
    print("Visit the following URL to authorize the app:")
    print(auth_url)
    webbrowser.open(auth_url)
    return input("Enter the authorization code: ").strip()

# Step 3: Exchange Authorization Code for Access Token
def get_access_token(authorization_code):
    token_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": authorization_code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    try:
        response = requests.post(TOKEN_URL, data=token_data)
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching token: {e}")
    return None

# Fetch User Teams with Names and Divisions
def get_user_teams_with_details(access_token):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    team_info = {}
    try:
        response = requests.get(USER_INFO_URL, headers=headers)
        response.raise_for_status()
        user_data = response.json()
        
        if "collection" in user_data and "items" in user_data["collection"]:
            for item in user_data["collection"]["items"]:
                for entry in item.get("data", []):
                    if entry.get("name") in ["managed_team_ids", "owned_team_ids", "commissioned_team_ids"]:
                        for team_id in entry.get("value", []):
                            team_info[team_id] = {"name": "Unknown Name", "division": "Unknown Division"}
        
        # Fetch team details to update names and divisions
        for team_id in team_info.keys():
            team_url = f"{TEAMS_URL}/{team_id}"
            try:
                team_response = requests.get(team_url, headers=headers)
                team_response.raise_for_status()
                team_data = team_response.json()
                if "collection" in team_data and "items" in team_data["collection"]:
                    for item in team_data["collection"]["items"]:
                        for entry in item.get("data", []):
                            if entry.get("name") == "name":
                                team_info[team_id]["name"] = entry.get("value", "Unknown Name")
                            elif entry.get("name") == "division_name":
                                team_info[team_id]["division"] = entry.get("value", "Unknown Division")
            except requests.exceptions.RequestException:
                pass
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user teams: {e}")
    return team_info

# Fetch Team Games (Events)
def get_team_games(access_token, team_id):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    params = {"team_id": team_id, "is_game": "true"}  # Ensure we fetch only games
    games = []
    try:
        response = requests.get(EVENTS_URL, headers=headers, params=params)
        response.raise_for_status()
        events_data = response.json()
        
        if "collection" in events_data and "items" in events_data["collection"]:
            for item in events_data["collection"]["items"]:
                game_details = {entry["name"]: entry["value"] for entry in item.get("data", []) if "name" in entry and "value" in entry}
                if game_details.get("is_game"):
                    games.append(game_details)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching games for team {team_id}: {e}")
    return games

# Example Usage
def main():
    authorization_code = get_authorization_code()
    access_token = get_access_token(authorization_code)
    
    if access_token:
        teams = get_user_teams_with_details(access_token)
        if teams:
            print("\nUser's Teams:")
            for team_id, details in teams.items():
                print(f"- ID: {team_id}, Name: {details['name']}, Division: {details['division']}")
                games = get_team_games(access_token, team_id)
                print("  Games Schedule:")
                if games:
                    for game in games:
                        start_time = game.get("start_time", "No Time")
                        if not start_time and "start_date" in game:
                            start_time = game["start_date"].split("T")[1] if "T" in game["start_date"] else "No Time"
                        print(f"    🏆 {game.get('name', 'Unknown Game')} - {game.get('start_date', 'No Date')} at {start_time}")
                else:
                    print("    No games found.")
        else:
            print("No teams found.")
    else:
        print("Failed to retrieve access token.")

if __name__ == "__main__":
    main()
