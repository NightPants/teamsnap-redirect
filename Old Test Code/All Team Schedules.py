#Outputs Team ID, Name and Divsion and all games for each team
#- ID: 9940707, Name: Shrewsbury Timber Rattlers, Division: Rookies BB 2025 (9U)
#  Games Schedule:
#    🏆 Sat 03/29/25 at 03:00 PM | Shrewsbury Graham 46/60 | vs Little Silver Grasshoppers
#    🏆 Wed 04/02/25 at 10:00 PM | Shrewsbury Manson | vs Shrewsbury Goats
#    🏆 Sat 04/05/25 at 03:00 PM | Shrewsbury Manson | vs Fair Haven Lugnuts
#    🏆 Wed 04/09/25 at 10:00 PM | Fair Haven Community Center South | vs Fair Haven Patriots
#    🏆 Sat 04/12/25 at 01:00 PM | Shrewsbury Manson | vs Little Silver Ironbirds
#    🏆 Wed 04/16/25 at 10:00 PM | Little Silver Firehouse Field | vs Little Silver Grasshoppers
#    🏆 Wed 04/30/25 at 10:00 PM | Rumson Riverside North | vs Rumson Tin Caps
#    🏆 Sat 05/03/25 at 01:00 PM | Shrewsbury Manson | vs Red Bank Space Cowboys
#    🏆 Wed 05/07/25 at 10:00 PM | Shrewsbury Graham 46/60 | vs Fair Haven Mussels
#    🏆 Wed 05/14/25 at 10:00 PM | Fair Haven Community Center South | vs Fair Haven Mussels
#    🏆 Sat 05/17/25 at 01:00 PM | Shrewsbury Manson | vs Rumson Red Wings
#    🏆 Wed 05/21/25 at 10:00 PM | Rumson Meadowridge South | vs Rumson Red Wings

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
            team_ids = []
            for item in user_data["collection"]["items"]:
                for entry in item.get("data", []):
                    if entry.get("name") in ["managed_team_ids", "owned_team_ids", "commissioned_team_ids"]:
                        team_ids.extend(entry.get("value", []))
            
            # Fetch team details
            for team_id in team_ids:
                team_info[team_id] = {"name": "Unknown Name", "division": "Unknown Division"}
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
                        start_date = game.get("start_date", "No Date")
                        location = game.get("location_name", "No Location")
                        opponent = game.get("opponent_name", "No Opponent")
                        
                        # Convert date format
                        try:
                            dt = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ")
                            formatted_date = dt.strftime("%a %m/%d/%y")
                            formatted_time = dt.strftime("%I:%M %p")
                        except ValueError:
                            formatted_date, formatted_time = start_date, start_time
                        
                        print(f"    🏆 {formatted_date} at {formatted_time} | {location} | vs {opponent}")
                else:
                    print("    No games found.")
        else:
            print("No teams found.")
    else:
        print("Failed to retrieve access token.")

if __name__ == "__main__":
    main()
