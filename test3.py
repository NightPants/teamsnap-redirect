import requests
import webbrowser

# Credentials and URLs
CLIENT_ID = "Eocrv5rmAg8v33ADCmM0dFS8dE4Vw6UJ5RdtIRDPojk"
CLIENT_SECRET = "xtIrH7i_doYM4Jj-jVlDXiBjCkqTT1wMmbHQa9tzGuM"
AUTH_URL = "https://auth.teamsnap.com/oauth/authorize"
TOKEN_URL = "https://auth.teamsnap.com/oauth/token"
REDIRECT_URI = "https://github.com/NightPants/teamsnap-redirect"

USER_INFO_URL = "https://api.teamsnap.com/v3/me"
EVENTS_URL = "https://api.teamsnap.com/v3/events"

# Step 1: Generate Authorization URL
def get_authorization_url():
    auth_params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "read write",
    }
    return f"{AUTH_URL}?{requests.compat.urlencode(auth_params)}"

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
    
    response = requests.post(TOKEN_URL, data=token_data)
    
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"Error fetching token. Status: {response.status_code}\n{response.text}")
        return None

# Step 4: Fetch User Info & Team IDs
def get_user_teams(access_token):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    response = requests.get(USER_INFO_URL, headers=headers)

    if response.status_code == 200:
        user_data = response.json()
        print("User data received from '/me' endpoint:")
        print(user_data)  # Print out the raw response for debugging
        team_ids = extract_team_ids(user_data)
        return team_ids
    else:
        print(f"Error fetching user info. Status: {response.status_code}\n{response.text}")
        return None

# Extract Team IDs from User Data
def extract_team_ids(data):
    team_ids = []
    if "collection" in data and "items" in data["collection"]:
        items = data["collection"]["items"]
        for item in items:
            if "data" in item:
                for entry in item["data"]:
                    if entry.get("name") == "teams":
                        team_ids.append(entry.get("value"))
    return team_ids

# Step 5: Fetch Events for Each Team
def get_team_events(access_token, team_ids):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    all_events = {}

    for team_id in team_ids:
        print(f"\nFetching events for Team ID: {team_id}")  # Output team ID being queried
        params = {"team_id": team_id}  # Filtering by team
        response = requests.get(EVENTS_URL, headers=headers, params=params)

        if response.status_code == 200:
            events_data = response.json()
            all_events[team_id] = parse_collection_json_list(events_data)
        else:
            print(f"Error fetching events for Team {team_id}. Status: {response.status_code}\n{response.text}")

    return all_events

# Parse Collection+JSON Format for a List of Items
def parse_collection_json_list(data):
    parsed_list = []
    if "collection" in data and "items" in data["collection"]:
        items = data["collection"]["items"]
        for item in items:
            event_details = {}
            for entry in item.get("data", []):
                event_details[entry["name"]] = entry["value"]
            parsed_list.append(event_details)

    return parsed_list

# Example Usage
def main():
    try:
        # Step 1: Get Authorization Code
        authorization_code = get_authorization_code()
        
        # Step 2: Get Access Token
        access_token = get_access_token(authorization_code)

        if access_token:
            print(f"Access Token: {access_token}")

            # Step 3: Fetch user teams
            team_ids = get_user_teams(access_token)
            if team_ids:
                print(f"User is part of Teams: {team_ids}")

                # Step 4: Fetch events for all teams
                all_team_events = get_team_events(access_token, team_ids)

                # Display events for all teams
                for team_id, events in all_team_events.items():
                    print(f"\n🔹 Team {team_id} Events:")
                    if events:
                        for event in events:
                            print("-" * 30)
                            print(f"📅 Event: {event.get('name', 'Unknown')}")
                            print(f"📍 Location: {event.get('location_name', 'Not Specified')}")
                            print(f"🕒 Start: {event.get('start_date', 'N/A')} at {event.get('start_time', 'N/A')}")
                            print(f"📅 End: {event.get('end_date', 'N/A')} at {event.get('end_time', 'N/A')}")
                            print(f"📌 Address: {event.get('address', 'N/A')}")
                            print(f"🏟️ City: {event.get('city', 'N/A')}, {event.get('state', 'N/A')}")
                    else:
                        print("No events found for this team.")
            else:
                print("No teams found.")
        else:
            print("Failed to retrieve access token.")

    except Exception as e:
        print("An error occurred:", str(e))

# Run the script
if __name__ == "__main__":
    main()
