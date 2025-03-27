import requests
import webbrowser
from urllib.parse import urlencode
from datetime import datetime
import csv
import json
import os
import pytz  # For time zone handling

# Credentials and URLs
CLIENT_ID = "Eocrv5rmAg8v33ADCmM0dFS8dE4Vw6UJ5RdtIRDPojk"
CLIENT_SECRET = "xtIrH7i_doYM4Jj-jVlDXiBjCkqTT1wMmbHQa9tzGuM"
AUTH_URL = "https://auth.teamsnap.com/oauth/authorize"
TOKEN_URL = "https://auth.teamsnap.com/oauth/token"
REDIRECT_URI = "https://github.com/NightPants/teamsnap-redirect"
USER_INFO_URL = "https://api.teamsnap.com/v3/me"
TEAMS_URL = "https://api.teamsnap.com/v3/teams"
EVENTS_URL = "https://api.teamsnap.com/v3/events/search"

TEAM_INFO_CSV_FILE = "team_info.csv"
LOCAL_TIMEZONE = pytz.timezone('America/New_York')  # Time zone for Red Bank, NJ

def load_team_info_from_csv():
    """Loads team information from a CSV file."""
    team_info = {}
    if os.path.exists(TEAM_INFO_CSV_FILE):
        try:
            with open(TEAM_INFO_CSV_FILE, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    team_info[row['team_id']] = {'name': row['name'], 'division': row['division']}
            return team_info
        except Exception as e:
            print(f"Error loading team info from CSV: {e}")
    return None

def save_team_info_to_csv(team_info):
    """Saves team information to a CSV file."""
    try:
        with open(TEAM_INFO_CSV_FILE, 'w', newline='') as csvfile:
            fieldnames = ['team_id', 'name', 'division']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for team_id, details in team_info.items():
                writer.writerow({'team_id': team_id, 'name': details['name'], 'division': details['division']})
        print("Team information saved to CSV.")
    except Exception as e:
        print(f"Error saving team info to CSV: {e}")

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
                for entry in item.get("data",):
                    if entry.get("name") in ["managed_team_ids", "owned_team_ids", "commissioned_team_ids"]:
                        team_ids.extend(entry.get("value",))

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
                            for entry in item.get("data",):
                                if entry.get("name") == "name":
                                    team_info[team_id]["name"] = entry.get("value", "Unknown Name")
                                elif entry.get("name") == "division_name":
                                    team_info[team_id]["division"] = entry.get("value", "Unknown Division")
                except requests.exceptions.RequestException:
                    pass
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user teams: {e}")
    return team_info

# Fetch Events for a Specific Date and sort by start time
def get_events_by_date(access_token, teams, target_date, event_type):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    all_events = []
    seen_events = set()  # To keep track of unique events

    for team_id, details in teams.items():
        params = {"team_id": team_id}
        if event_type.lower() == "games":
            params["is_game"] = "true"
        elif event_type.lower() == "practices":
            params["is_game"] = "false"
        # If event_type is "All", no specific parameters are added

        try:
            response = requests.get(EVENTS_URL, headers=headers, params=params)
            response.raise_for_status()
            events_data = response.json()

            if "collection" in events_data and "items" in events_data["collection"]:
                for item in events_data["collection"]["items"]:
                    event_id = None
                    is_game_flag = False
                    is_league_controlled = None
                    event_details = {}
                    time_zone_str = None
                    for entry in item.get("data",):
                        event_details[entry["name"]] = entry["value"]
                        if entry["name"] == "is_game":
                            is_game_flag = entry["value"]
                        elif entry["name"] == "id":
                            event_id = entry["value"]
                        elif entry["name"] == "is_league_controlled":
                            is_league_controlled = entry["value"]
                        elif entry["name"] == "time_zone":
                            time_zone_str = entry["value"]

                    include_event = False
                    if event_type.lower() == "games" and is_game_flag:
                        include_event = True
                    elif event_type.lower() == "practices" and not is_game_flag:
                        include_event = True
                    elif event_type.lower() == "all":
                        include_event = True

                    if include_event:
                        try:
                            start_time_str = event_details.get("start_date")
                            location = event_details.get("location_name", "No Location")
                            opponent = event_details.get("opponent_name", "N/A") # Opponent might not be relevant for practices
                            current_team = details['name']

                            if start_time_str and time_zone_str:
                                if time_zone_str == 'Eastern Time (US & Canada)':
                                    event_timezone = pytz.timezone('America/New_York')
                                else:
                                    event_timezone = pytz.timezone(time_zone_str)
                                utc_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
                                local_time = utc_time.astimezone(event_timezone).astimezone(LOCAL_TIMEZONE)
                                local_time_str_display = local_time.strftime("%I:%M %p")
                                local_date_str_display = local_time.strftime("%m/%d/%y")
                                local_day_str_display = local_time.strftime("%a")

                                if local_date_str_display == target_date:
                                    # Create a unique identifier for the event
                                    event_identifier = (event_id, local_time)

                                    if event_identifier not in seen_events:
                                        all_events.append({
                                            "full_item": item,  # Store the entire item
                                            "id": event_id,
                                            "day": local_day_str_display,
                                            "date": local_date_str_display,
                                            "time": local_time_str_display,
                                            "location": location,
                                            "division": details['division'],
                                            "team_name": current_team,
                                            "opponent": opponent if is_game_flag else "N/A",
                                            "start_datetime": local_time,
                                            "game_type_code": event_details.get("game_type_code", "N/A"),
                                            "is_canceled": event_details.get("is_canceled", "N/A"),
                                            "is_game": is_game_flag,
                                            "is_league_controlled": is_league_controlled
                                        })
                                        seen_events.add(event_identifier)
                        except ValueError:
                            pass
        except requests.exceptions.RequestException as e:
            print(f"Error fetching events for team {team_id}: {e}")

    # Sort events by start time
    all_events.sort(key=lambda x: x["start_datetime"])
    return all_events

def filter_games_by_town(games, selected_town): # Renamed to filter_events_by_town for consistency but keeping function name for now
    filtered_games = []
    towns = ["Rumson", "Little Silver", "Red Bank", "Fair Haven", "Shrewsbury"]

    if selected_town in towns:
        for game in games:
            if selected_town.lower() in game['location'].lower():
                filtered_games.append(game)
    elif selected_town.lower() == 'other':
        for game in games:
            is_other = True
            for town in towns:
                if town.lower() in game['location'].lower():
                    is_other = False
                    break
            if is_other:
                filtered_games.append(game)
    else:
        return games  # Return all if no valid filter

    return filtered_games

# Example Usage
def main():
    stored_team_info = load_team_info_from_csv()
    use_stored_teams = False

    if stored_team_info:
        choice = input("Do you want to (u)pdate team information or (s)use stored team information? (u/s): ").strip().lower()
        if choice == 's':
            teams = stored_team_info
            use_stored_teams = True
            print("Using stored team information.")
        else:
            print("Updating team information from the API.")
    else:
        print("No stored team information found. Fetching from the API.")

    # Always get the access token
    authorization_code = get_authorization_code()
    access_token = get_access_token(authorization_code)

    if not access_token:
        print("Failed to retrieve access token. Exiting.")
        return

    if not use_stored_teams:
        teams = get_user_teams_with_details(access_token)
        if teams:
            save_team_info_to_csv(teams)
        else:
            print("No teams found.")
            return
    elif not stored_team_info:
        teams = get_user_teams_with_details(access_token)
        if teams:
            save_team_info_to_csv(teams)
        else:
            print("No teams found.")
            return
    else:
        print("Using loaded team information.")

    if teams:
        while True:
            target_date_str = input("Enter a date (MM/DD/YY) to filter events: ").strip()
            try:
                datetime.strptime(target_date_str, "%m/%d/%y")
                target_date = target_date_str

                while True:
                    event_type = input("Filter by (G)ames, (P)ractices, or (A)ll? (g/p/a): ").strip().lower()
                    if event_type in ['g', 'p', 'a']:
                        if event_type == 'g':
                            event_type_str = "Games"
                        elif event_type == 'p':
                            event_type_str = "Practices"
                        else:
                            event_type_str = "All"
                        break
                    else:
                        print("Invalid selection. Please enter 'g', 'p', or 'a'.")

                events = get_events_by_date(access_token, teams, target_date, event_type_str)

                filter_by_town_choice = input("Do you want to filter results by town? (y/n): ").strip().lower()
                if filter_by_town_choice == 'y':
                    print("\nSelect a town to filter by:")
                    town_options = ["Rumson", "Little Silver", "Red Bank", "Fair Haven", "Shrewsbury", "Other"]
                    for i, town in enumerate(town_options):
                        print(f"{i+1}. {town}")
                    while True:
                        try:
                            town_selection = input("Enter the number of the town: ").strip()
                            if town_selection.isdigit():
                                selection_index = int(town_selection) - 1
                                if 0 <= selection_index < len(town_options):
                                    selected_town = town_options[selection_index]
                                    events = filter_games_by_town(events, selected_town) # Still using the old function name
                                    break
                                else:
                                    print("Invalid selection. Please enter a number from the list.")
                            else:
                                print("Invalid input. Please enter a number.")
                        except ValueError:
                            print("Invalid input. Please enter a number.")

                print(f"\n{event_type_str} on {target_date}:")
                if events:
                    for event in events:
                        event_display = f"    🏆 ID: {event.get('id', 'N/A')} | {event['day']} {event['date']} at {event['time']} | {event['location']} | {event['division']} | {event['team_name']}"
                        if event['is_game']:
                            event_display += f" vs {event['opponent']} | Type: {event.get('game_type_code', 'N/A')}, Canceled: {event.get('is_canceled', 'N/A')}, Is Game: {event.get('is_game', 'N/A')}, League Controlled: {event.get('is_league_controlled', 'N/A')}"
                        else:
                            event_display += f" | Practice"
                        print(event_display)

                        # --- RAW JSON OUTPUT (COMMENTED OUT) ---
                        # print("        Raw JSON Response:")
                        # print(json.dumps(event['full_item'], indent=4))
                        # print("-" * 40)
                        # --- END OF COMMENTED OUT SECTION ---

                    export_to_csv = input("\nDo you want to export the results to a CSV file? (y/n): ").strip().lower()
                    if export_to_csv == 'y':
                        csv_filename = input("Enter the filename for the CSV (e.g., events.csv): ").strip()
                        try:
                            with open(csv_filename, 'w', newline='') as csvfile:
                                fieldnames = ['ID', 'Day', 'Date', 'Time', 'Location', 'Division', 'Team Name', 'Opponent', 'Game Type Code', 'Is Canceled', 'Is Game', 'League Controlled']
                                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                                writer.writeheader()
                                for event in events:
                                    writer.writerow({
                                        'ID': event.get('id', ''),
                                        'Day': event['day'],
                                        'Date': event['date'],
                                        'Time': event['time'],
                                        'Location': event['location'],
                                        'Division': event['division'],
                                        'Team Name': event['team_name'],
                                        'Opponent': event.get('opponent', ''),
                                        'Game Type Code': event.get('game_type_code', ''),
                                        'Is Canceled': event.get('is_canceled', ''),
                                        'Is Game': event.get('is_game', ''),
                                        'League Controlled': event.get('is_league_controlled', '')
                                    })
                            print(f"Results exported to '{csv_filename}' successfully.")
                        except Exception as e:
                            print(f"Error exporting to CSV: {e}")
                else:
                    print(f"    No {event_type_str.lower()} found for this date.")
            except ValueError:
                print("Invalid date format. Please use MM/DD/YY.")

            run_again = input("\nDo you want to check events for another date? (y/n): ").strip().lower()
            if run_again != 'y':
                break
    else:
        print("No team information available.")

if __name__ == "__main__":
    main()