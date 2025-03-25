import requests
import webbrowser
from urllib.parse import urlencode
from datetime import datetime
import csv

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

# Fetch Games for a Specific Date and sort by start time
def get_games_by_date(access_token, teams, target_date):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    all_games = []
    for team_id, details in teams.items():
        params = {"team_id": team_id, "is_game": "true"}
        try:
            response = requests.get(EVENTS_URL, headers=headers, params=params)
            response.raise_for_status()
            events_data = response.json()

            if "collection" in events_data and "items" in events_data["collection"]:
                for item in events_data["collection"]["items"]:
                    game_details = {entry["name"]: entry["value"] for entry in item.get("data",) if "name" in entry and "value" in entry}
                    if game_details.get("is_game"):
                        try:
                            start_time_str = game_details.get("start_date")
                            if start_time_str:
                                dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%SZ")
                                game_date = dt.strftime("%m/%d/%y")
                                if game_date == target_date:
                                    formatted_time = dt.strftime("%I:%M %p")
                                    all_games.append({
                                        "day": dt.strftime("%a"),
                                        "date": game_date,
                                        "time": formatted_time,
                                        "location": game_details.get("location_name", "No Location"),
                                        "division": details['division'],
                                        "team_name": details['name'],
                                        "opponent": game_details.get("opponent_name", "No Opponent"),
                                        "start_datetime": dt,
                                        "game_type_code": game_details.get("game_type_code"),
                                        "is_canceled": game_details.get("is_canceled"),
                                        "is_game": game_details.get("is_game")
                                    })
                        except ValueError:
                            pass
        except requests.exceptions.RequestException as e:
            print(f"Error fetching games for team {team_id}: {e}")

    # Sort games by start time
    all_games.sort(key=lambda x: x["start_datetime"])
    return all_games

# Example Usage
def main():
    authorization_code = get_authorization_code()
    access_token = get_access_token(authorization_code)

    if access_token:
        teams = get_user_teams_with_details(access_token)
        if teams:
            target_date_str = input("Enter a date (MM/DD/YY) to filter games: ").strip()
            try:
                datetime.strptime(target_date_str, "%m/%d/%y")
                target_date = target_date_str
                games = get_games_by_date(access_token, teams, target_date)

                print(f"\nGames on {target_date}:")
                if games:
                    for game in games:
                        print(f"    🏆 {game['day']} {game['date']} at {game['time']} | {game['location']} | {game['division']} | {game['team_name']} vs {game['opponent']} | Type: {game.get('game_type_code', 'N/A')}, Canceled: {game.get('is_canceled', 'N/A')}, Is Game: {game.get('is_game', 'N/A')}")

                    export_to_csv = input("\nDo you want to export the results to a CSV file? (yes/no): ").strip().lower()
                    if export_to_csv == 'yes':
                        csv_filename = input("Enter the filename for the CSV (e.g., games.csv): ").strip()
                        try:
                            with open(csv_filename, 'w', newline='') as csvfile:
                                fieldnames = ['Day', 'Date', 'Time', 'Location', 'Division', 'Team Name', 'Opponent', 'Game Type Code', 'Is Canceled', 'Is Game']
                                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                                writer.writeheader()
                                for game in games:
                                    writer.writerow({
                                        'Day': game['day'],
                                        'Date': game['date'],
                                        'Time': game['time'],
                                        'Location': game['location'],
                                        'Division': game['division'],
                                        'Team Name': game['team_name'],
                                        'Opponent': game['opponent'],
                                        'Game Type Code': game.get('game_type_code', ''),
                                        'Is Canceled': game.get('is_canceled', ''),
                                        'Is Game': game.get('is_game', '')
                                    })
                                print(f"Results exported to '{csv_filename}' successfully.")
                        except Exception as e:
                            print(f"Error exporting to CSV: {e}")
                else:
                    print("    No games found for this date.")
            except ValueError:
                print("Invalid date format. Please use MM/DD/YY.")
        else:
            print("No teams found.")
    else:
        print("Failed to retrieve access token.")

if __name__ == "__main__":
    main()