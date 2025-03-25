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

# Fetch Games for a Specific Date
def get_games_by_date(access_token, teams, target_date):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    filtered_games = []
    
    for team_id, details in teams.items():
        params = {"team_id": team_id, "is_game": "true"}
        try:
            response = requests.get(EVENTS_URL, headers=headers, params=params)
            response.raise_for_status()
            events_data = response.json()
            
            if "collection" in events_data and "items" in events_data["collection"]:
                for item in events_data["collection"]["items"]:
                    game_details = {entry["name"]: entry["value"] for entry in item.get("data", []) if "name" in entry and "value" in entry}
                    if game_details.get("is_game"):
                        try:
                            dt = datetime.strptime(game_details.get("start_date", ""), "%Y-%m-%dT%H:%M:%SZ")
                            game_date = dt.strftime("%m/%d/%y")
                            if game_date == target_date:
                                formatted_time = dt.strftime("%I:%M %p")
                                filtered_games.append((
                                    dt.strftime("%a"), game_date, formatted_time, 
                                    game_details.get("location_name", "No Location"), 
                                    details['division'], details['name'], 
                                    game_details.get("opponent_name", "No Opponent")
                                ))
                        except ValueError:
                            pass
        except requests.exceptions.RequestException as e:
            print(f"Error fetching games for team {team_id}: {e}")
    return filtered_games

# Example Usage
def main():
    authorization_code = get_authorization_code()
    access_token = get_access_token(authorization_code)
    
    if access_token:
        teams = get_user_teams_with_details(access_token)
        if teams:
            target_date = input("Enter a date (MM/DD/YY) to filter games: ").strip()
            games = get_games_by_date(access_token, teams, target_date)
            
            print(f"\nGames on {target_date}:")
            if games:
                for game in games:
                    print(f"    🏆 {game[0]} {game[1]} at {game[2]} | {game[3]} | {game[4]} | {game[5]} vs {game[6]}")
            else:
                print("    No games found for this date.")
        else:
            print("No teams found.")
    else:
        print("Failed to retrieve access token.")

if __name__ == "__main__":
    main()
