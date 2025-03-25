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
EVENTS_URL = "https://api.teamsnap.com/v3/events"
TEAMS_URL = "https://api.teamsnap.com/v3/teams" # New URL for fetching team details

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

# Step 4: Fetch User Info & Team IDs and Names
def get_user_teams_with_names(access_token):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    team_info = {}
    team_ids = []

    try:
        response_me = requests.get(USER_INFO_URL, headers=headers)
        response_me.raise_for_status()
        user_data = response_me.json()
        print("User data received from '/me' endpoint:")
        # print(user_data)

        team_ids = extract_team_ids(user_data)

        if team_ids:
            print("\nFetching team details...")
            for team_id in team_ids:
                team_detail_url = f"{TEAMS_URL}/{team_id}"
                try:
                    response_team = requests.get(team_detail_url, headers=headers)
                    response_team.raise_for_status()
                    team_data = response_team.json()
                    team_name = ""
                    if isinstance(team_data, dict) and "data" in team_data and isinstance(team_data.get("data"), list) and len(team_data["data"]) > 0:
                        for item in team_data["data"]:
                            if isinstance(item, dict) and item.get("name") == "name":
                                team_name = item.get("value")
                                break
                    elif isinstance(team_data, dict) and "collection" in team_data and isinstance(team_data.get("collection"), dict) and "items" in team_data["collection"] and len(team_data["collection"]["items"]) > 0:
                        for item in team_data["collection"]["items"]:
                            if isinstance(item, dict) and "data" in item and isinstance(item.get("data"), list):
                                for entry in item["data"]:
                                    if isinstance(entry, dict) and entry.get("name") == "name":
                                        team_name = entry.get("value")
                                        break
                                if team_name:
                                    break
                    if team_name:
                        team_info[team_id] = team_name
                    else:
                        team_info[team_id] = "Unknown Name"
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching details for team {team_id}: {e}")
                    team_info[team_id] = f"Error fetching name"
                except (KeyError, IndexError, TypeError):
                    print(f"Could not parse team details for {team_id}")
                    team_info[team_id] = "Could not parse name"
            return team_info
        else:
            print("No team IDs found for this user.")
            return {}

    except requests.exceptions.RequestException as e:
        print(f"Error fetching user info: {e}")
    except ValueError:
        print("Error decoding JSON response from /me endpoint.")
    return None

# Extract Team IDs from User Data
def extract_team_ids(data):
    team_ids = []
    if isinstance(data, dict) and "collection" in data and isinstance(data["collection"], dict) and "items" in data["collection"] and isinstance(data["collection"]["items"], list):
        for item in data["collection"]["items"]:
            if isinstance(item, dict) and "data" in item and isinstance(item["data"], list):
                for entry in item["data"]:
                    if isinstance(entry, dict):
                        if entry.get("name") == "managed_team_ids" and isinstance(entry.get("value"), list):
                            team_ids.extend(entry.get("value"))
                        elif entry.get("name") == "owned_team_ids" and isinstance(entry.get("value"), list):
                            team_ids.extend(entry.get("value"))
                        elif entry.get("name") == "commissioned_team_ids" and isinstance(entry.get("value"), list):
                            team_ids.extend(entry.get("value"))
    return team_ids

# Step 5: Fetch Events for Each Team
def get_team_events(access_token, team_ids_with_names):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    all_events = {}

    for team_id, team_name in team_ids_with_names.items():
        print(f"\nFetching events for Team ID: {team_id} ({team_name if team_name else 'Unknown Name'})")
        params = {"team_id": team_id}
        try:
            response = requests.get(EVENTS_URL, headers=headers, params=params)
            response.raise_for_status()
            events_data = response.json()
            all_events[team_id] = parse_collection_json_list(events_data)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching events for Team {team_id}: {e}")
            all_events[team_id] = []
        except ValueError:
            print(f"Error decoding JSON response for Team {team_id}.")
            all_events[team_id] = []

    return all_events

# Parse Collection+JSON Format for a List of Items
def parse_collection_json_list(data):
    parsed_list = []
    if isinstance(data, dict) and "collection" in data and isinstance(data["collection"], dict) and "items" in data["collection"] and isinstance(data["collection"]["items"], list):
        for item in data["collection"]["items"]:
            event_details = {}
            if isinstance(item, dict) and "data" in item and isinstance(item.get("data"), list):
                for entry in item["data"]:
                    if isinstance(entry, dict) and "name" in entry and "value" in entry:
                        event_details[entry["name"]] = entry["value"]

                # Convert date and time strings to datetime objects for better handling
                start_date_str = event_details.get("start_date")
                start_time_str = event_details.get("start_time")
                end_date_str = event_details.get("end_date")
                end_time_str = event_details.get("end_time")

                if start_date_str and start_time_str:
                    try:
                        event_details["start_datetime"] = datetime.strptime(f"{start_date_str} {start_time_str}", "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        event_details["start_datetime"] = None
                else:
                    event_details["start_datetime"] = None

                if end_date_str and end_time_str:
                    try:
                        event_details["end_datetime"] = datetime.strptime(f"{end_date_str} {end_time_str}", "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        event_details["end_datetime"] = None
                else:
                    event_details["end_datetime"] = None

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

            # Step 3: Fetch user teams with names
            team_info = get_user_teams_with_names(access_token)
            if team_info:
                print(f"User is part of Teams:")
                for team_id, team_name in team_info.items():
                    print(f"- ID: {team_id}, Name: {team_name}")

                # Step 4: Fetch events for all teams
                all_team_events = get_team_events(access_token, team_info)

                # Display events for all teams
                for team_id, events in all_team_events.items():
                    team_name = team_info.get(team_id, "Unknown Name")
                    print(f"\n🔹 Team {team_id} ({team_name}) Events:")
                    if events:
                        for event in events:
                            print("-" * 30)
                            print(f"📅 Event: {event.get('name', 'Unknown')}")
                            print(f"📍 Location: {event.get('location_name', 'Not Specified')}")
                            print(f"🕒 Start: {event.get('start_date', 'N/A')} at {event.get('start_time', 'N/A')}")
                            print(f"📅 End: {event.get('end_date', 'N/A')} at {event.get('end_time', 'N/A')}")
                            print(f"📌 Address: {event.get('address', 'N/A')}")
                            print(f"🏟️ City: {event.get('city', 'N/A')}, {event.get('state', 'N/A')}")
                            if 'start_datetime' in event and event['start_datetime']:
                                print(f"🗓️ Start (Datetime): {event['start_datetime']}")
                            if 'end_datetime' in event and event['end_datetime']:
                                print(f"🗓️ End (Datetime): {event['end_datetime']}")
                    else:
                        print("No events found for this team.")
            else:
                print("No teams found for this user.")
        else:
            print("Failed to retrieve access token.")

    except Exception as e:
        print("An error occurred:", str(e))

# Run the script
if __name__ == "__main__":
    main()