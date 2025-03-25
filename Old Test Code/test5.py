# Team ID's, Names, Division

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
EVENTS_URL = "https://api.teamsnap.com/v3/events"

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
    except ValueError:
        print("Error decoding JSON response from token endpoint.")
    return None

# Fetch User Teams with Names and Divisions
def get_user_teams_with_details(access_token):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    team_info = {}
    team_ids = []

    try:
        response_me = requests.get(USER_INFO_URL, headers=headers)
        response_me.raise_for_status()
        user_data = response_me.json()
        team_ids = extract_team_ids(user_data)

        if team_ids:
            for team_id in team_ids:
                team_detail_url = f"{TEAMS_URL}/{team_id}"
                try:
                    response_team = requests.get(team_detail_url, headers=headers)
                    response_team.raise_for_status()
                    team_data = response_team.json()

                    team_name, division = "Unknown Name", "Unknown Division"
                    if "collection" in team_data and "items" in team_data["collection"]:
                        for item in team_data["collection"]["items"]:
                            if "data" in item:
                                for entry in item["data"]:
                                    if entry.get("name") == "name":
                                        team_name = entry.get("value", "Unknown Name")
                                    elif entry.get("name") == "division_name":
                                        division = entry.get("value", "Unknown Division")
                    
                    team_info[team_id] = {"name": team_name, "division": division}
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching details for team {team_id}: {e}")
                    team_info[team_id] = {"name": "Error fetching name", "division": "Error fetching division"}
        else:
            print("No team IDs found for this user.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user info: {e}")
    return team_info

# Extract Team IDs from User Data
def extract_team_ids(data):
    team_ids = []
    if isinstance(data, dict) and "collection" in data:
        for item in data["collection"].get("items", []):
            for entry in item.get("data", []):
                if entry.get("name") in ["managed_team_ids", "owned_team_ids", "commissioned_team_ids"]:
                    team_ids.extend(entry.get("value", []))
    return team_ids

# Fetch Team Schedule (Events)
def get_team_schedule(access_token, team_id):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    events = []
    params = {"team_id": team_id}
    try:
        response = requests.get(EVENTS_URL, headers=headers, params=params)
        response.raise_for_status()
        events_data = response.json()
        if "collection" in events_data and "items" in events_data["collection"]:
            for item in events_data["collection"]["items"]:
                event_details = {}
                for entry in item.get("data", []):
                    if "name" in entry and "value" in entry:
                        event_details[entry["name"]] = entry["value"]
                events.append(event_details)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching schedule for team {team_id}: {e}")
    return events

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
                schedule = get_team_schedule(access_token, team_id)
                print("  Schedule:")
                for event in schedule:
                    print(f"    📅 {event.get('name', 'Unknown Event')} - {event.get('start_date', 'No Date')} at {event.get('start_time', 'No Time')}")
        else:
            print("No teams found.")
    else:
        print("Failed to retrieve access token.")

if __name__ == "__main__":
    main()