import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.filedialog import asksaveasfilename
from urllib.parse import urlencode
from datetime import datetime
import requests
import webbrowser
import pytz
import csv
import os
import json
from tkcalendar import Calendar
import threading

def get_authorization_url():
    auth_params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "read write",
    }
    return f"{AUTH_URL}?{urlencode(auth_params)}"

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

def get_events_by_date(access_token, teams, target_date, event_type, progress_callback=None):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    all_events = []
    seen_events = set()  # To keep track of unique events
    total_teams = len(teams)
    team_count = 0

    for team_id, details in teams.items():
        team_count += 1
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
                            division = details['division']

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
                                            "division": division,
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

        if progress_callback:
            progress_callback(team_count, total_teams)

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

# --- END OF FUNCTION DEFINITIONS ---

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
LOCAL_TIMEZONE = pytz.timezone('America/New_York')

access_token = None
teams = None
stored_team_info = None
use_stored_teams = False
events_data = [] # To store fetched events for export
export_button = None # Initialize the export button
refresh_now_button = None
progress_bar = None

def authenticate():
    auth_url = get_authorization_url()
    webbrowser.open(auth_url)
    auth_button.pack_forget() # Hide the authenticate button
    auth_code_frame.pack(pady=10) # Show the authentication code input frame

def submit_auth_code():
    global access_token, teams, auth_status_label, stored_team_info
    code = auth_code_entry.get()
    access_token = get_access_token(code)
    if access_token:
        auth_status_label.config(text="Authentication Status: Authenticated", foreground="green")
        messagebox.showinfo("Success", "Successfully obtained access token.")
        auth_code_frame.pack_forget() # Hide the input fields
        # Load team info based on selection after successful auth
        if team_info_choice.get() == "existing":
            global stored_team_info, teams
            stored_team_info = load_team_info_from_csv()
            if stored_team_info:
                teams = stored_team_info
                messagebox.showinfo("Info", "Using existing team information.")
            else:
                messagebox.showinfo("Info", "No stored team information found. Please refresh teams.")
        elif team_info_choice.get() == "refresh":
            # Do nothing here, the "Refresh Now" button will handle it
            pass
    else:
        auth_status_label.config(text="Authentication Status: Failed", foreground="red")
        messagebox.showerror("Error", "Failed to retrieve access token.")

def refresh_teams_now():
    global access_token, teams
    if not access_token:
        messagebox.showerror("Error", "Please authenticate first.")
        return
    teams = get_user_teams_with_details(access_token)
    if teams:
        save_team_info_to_csv(teams)
        messagebox.showinfo("Info", "Team information refreshed.")
    else:
        messagebox.showerror("Error", "Could not retrieve team information.")

def team_info_choice_changed():
    global refresh_now_button
    if team_info_choice.get() == "refresh":
        if refresh_now_button is None:
            refresh_now_button = ttk.Button(team_info_frame, text="Refresh Now", command=refresh_teams_now)
            refresh_now_button.pack(side=tk.LEFT, padx=5, pady=5)
        elif refresh_now_button.winfo_ismapped() == 0:
            refresh_now_button.pack(side=tk.LEFT, padx=5, pady=5)
    else:
        if refresh_now_button is not None and refresh_now_button.winfo_ismapped() == 1:
            refresh_now_button.pack_forget()

def update_progress_bar(current, total):
    global progress_bar
    if progress_bar:
        progress_bar['value'] = current
        progress_bar['maximum'] = total
        root.update_idletasks()

def fetch_events_threaded():
    global access_token, teams, events_data, cal, results_tree, export_button, progress_bar, fetch_button

    selected_date = cal.get_date()
    target_date = datetime.strptime(selected_date, "%m/%d/%y").strftime("%m/%d/%y") # Format to MM/DD/YY

    event_type = event_type_var.get()
    event_type_str = ""
    if event_type == 'Games':
        event_type_str = "Games"
    elif event_type == 'Practices':
        event_type_str = "Practices"
    else:
        event_type_str = "All"

    selected_town = town_var.get()

    try:
        datetime.strptime(target_date, "%m/%d/%y")
        events = get_events_by_date(access_token, teams, target_date, event_type_str, progress_callback=update_progress_bar)
        events_data = events # Store for potential export

        if selected_town != "No Filter":
            events = filter_games_by_town(events, selected_town)

        root.after(0, populate_results_table, events) # Update UI on main thread

    except ValueError as e:
        root.after(0, lambda: messagebox.showerror("Error", f"Invalid date format: {e}"))
    finally:
        root.after(0, finalize_fetch_events)

def populate_results_table(events):
    global results_tree, export_button
    # Clear previous results from the table
    for item in results_tree.get_children():
        results_tree.delete(item)

    if events:
        for event in events:
            results_tree.insert("", tk.END, values=(
                event['time'],
                event['location'],
                event['team_name'],
                event.get('opponent', 'N/A') if event['is_game'] else "N/A",
                event['division'],
                "Game" if event['is_game'] else "Practice"
            ))
        # Show the export button if results are present
        if export_button is None:
            export_button = ttk.Button(button_frame, text="Export to CSV", command=export_events_to_csv)
            export_button.pack(side=tk.LEFT, padx=5)
        elif export_button.winfo_ismapped() == 0: # Check if not already visible
            export_button.pack(side=tk.LEFT, padx=5)
    else:
        messagebox.showinfo("Info", f"No {event_type_str.lower()} found for this date.")
        # Hide the export button if no results
        if export_button is not None and export_button.winfo_ismapped() == 1:
            export_button.pack_forget()

def finalize_fetch_events():
    global progress_bar, fetch_button
    if progress_bar:
        progress_bar.destroy()
        progress_bar = None
    fetch_button.config(state=tk.NORMAL)

def fetch_events():
    global fetch_button, progress_bar, access_token, teams
    if not access_token:
        messagebox.showerror("Error", "Please authenticate first.")
        return
    if teams is None:
        messagebox.showerror("Error", "Please select an option for team information.")
        return

    fetch_button.config(state=tk.DISABLED) # Disable the button during fetching

    # Create and pack the progress bar
    if progress_bar is None:
        progress_bar = ttk.Progressbar(root, orient=tk.HORIZONTAL, length=200, mode='determinate')
        progress_bar.pack(pady=10)
    elif progress_bar.winfo_ismapped() == 0:
        progress_bar.pack(pady=10)

    thread = threading.Thread(target=fetch_events_threaded)
    thread.start()

def export_events_to_csv():
    if not events_data:
        messagebox.showinfo("Info", "No events fetched to export.")
        return

    filename = asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
    if filename:
        try:
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['Time', 'Location', 'Team Name', 'Opponent', 'Division', 'Event Type', 'Game Type Code', 'Is Canceled', 'Is League Controlled']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for event in events_data:
                    writer.writerow({
                        'Time': event['time'],
                        'Location': event['location'],
                        'Team Name': event['team_name'],
                        'Opponent': event.get('opponent', ''),
                        'Division': event['division'],
                        'Event Type': "Game" if event.get('is_game') else "Practice",
                        'Game Type Code': event.get('game_type_code', ''),
                        'Is Canceled': event.get('is_canceled', ''),
                        'League Controlled': event.get('is_league_controlled', '')
                    })
            messagebox.showinfo("Success", f"Results exported to '{filename}' successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Error exporting to CSV: {e}")

def ask_run_again():
    run_again_window = tk.Toplevel(root)
    run_again_window.title("Check Another Date?")
    yes_button = ttk.Button(run_again_window, text="Yes", command=reset_for_another_date)
    yes_button.pack(side=tk.LEFT, padx=10, pady=10)
    no_button = ttk.Button(run_again_window, text="No", command=root.quit)
    no_button.pack(side=tk.RIGHT, padx=10, pady=10)

def reset_for_another_date():
    global cal, export_button, refresh_now_button, progress_bar, fetch_button
    cal.set_date(datetime.now().date()) # Reset to current date
    event_type_var.set("All")
    town_var.set("No Filter")
    # Clear results table
    for item in results_tree.get_children():
        results_tree.delete(item)
    # Hide the export button
    if export_button is not None and export_button.winfo_ismapped() == 1:
        export_button.pack_forget()
    # Hide the refresh now button
    if refresh_now_button is not None and refresh_now_button.winfo_ismapped() == 1:
        refresh_now_button.pack_forget()
    # Ensure progress bar is removed
    if progress_bar is not None:
        progress_bar.destroy()
        progress_bar = None
    fetch_button.config(state=tk.NORMAL)
    ask_run_again_window.destroy()

# --- GUI Setup ---
root = tk.Tk()
root.title("Teamsnap Event Viewer")

# Authentication Status
auth_status_label = ttk.Label(root, text="Authentication Status: Not Authenticated", foreground="red")
auth_status_label.pack(pady=5)

# Authentication Button
auth_button = ttk.Button(root, text="Authenticate with Teamsnap", command=authenticate)
auth_button.pack(pady=10)

# Authentication Code Input Frame (initially hidden)
auth_code_frame = ttk.LabelFrame(root, text="Enter Authorization Code")
auth_code_entry = ttk.Entry(auth_code_frame)
auth_code_entry.pack(padx=10, pady=5)
submit_auth_code_button = ttk.Button(auth_code_frame, text="Submit Code", command=submit_auth_code)
submit_auth_code_button.pack(pady=5)
auth_code_frame.pack_forget() # Initially hidden

# Team Info Handling
team_info_frame = ttk.LabelFrame(root, text="Team Information")
team_info_frame.pack(padx=10, pady=10, fill="x")

team_info_choice = tk.StringVar(value="existing") # Default to use existing
team_info_choice.trace_add("write", lambda *args: team_info_choice_changed()) # Trace changes to the radio buttons

use_existing_radio = ttk.Radiobutton(team_info_frame, text="Use Existing Team Info", variable=team_info_choice, value="existing")
use_existing_radio.pack(side=tk.LEFT, padx=5, pady=5)

refresh_teams_radio = ttk.Radiobutton(team_info_frame, text="Refresh Teams", variable=team_info_choice, value="refresh")
refresh_teams_radio.pack(side=tk.LEFT, padx=5, pady=5)

# Date Selection using Calendar
date_frame = ttk.LabelFrame(root, text="Select Date")
date_frame.pack(padx=10, pady=10, fill="x")

cal = Calendar(date_frame, selectmode='day',
                year=datetime.now().year,
                month=datetime.now().month,
                day=datetime.now().day)
cal.pack(pady=10)

# Event Type Selection
event_type_frame = ttk.LabelFrame(root, text="Filter by Event Type")
event_type_frame.pack(padx=10, pady=10, fill="x")

event_type_var = tk.StringVar(value="All")
games_radio = ttk.Radiobutton(event_type_frame, text="Games", variable=event_type_var, value="Games")
games_radio.pack(side=tk.LEFT, padx=5)
practices_radio = ttk.Radiobutton(event_type_frame, text="Practices", variable=event_type_var, value="Practices")
practices_radio.pack(side=tk.LEFT, padx=5)
all_radio = ttk.Radiobutton(event_type_frame, text="All", variable=event_type_var, value="All")
all_radio.pack(side=tk.LEFT, padx=5)

# Town Selection
town_frame = ttk.LabelFrame(root, text="Filter by Town")
town_frame.pack(padx=10, pady=10, fill="x")

town_options = ["No Filter", "Rumson", "Little Silver", "Red Bank", "Fair Haven", "Shrewsbury", "Other"]
town_var = tk.StringVar(value="No Filter")
town_combo = ttk.Combobox(town_frame, textvariable=town_var, values=town_options)
town_combo.pack(padx=5, pady=5)

# Fetch and Export Buttons Frame
button_frame = ttk.Frame(root)
button_frame.pack(pady=10)

# Fetch Events Button
fetch_button = ttk.Button(button_frame, text="Fetch Events", command=fetch_events)
fetch_button.pack(side=tk.LEFT, padx=5)

# Results Display in a Table
results_label = ttk.Label(root, text="Event Results:")
results_label.pack()
results_tree = ttk.Treeview(root, columns=("Time", "Location", "Team", "Opponent", "Division", "Type"), show="headings")
results_tree.heading("Time", text="Time")
results_tree.heading("Location", text="Location")
results_tree.heading("Team", text="Team")
results_tree.heading("Opponent", text="Opponent")
results_tree.heading("Division", text="Division")
results_tree.heading("Type", text="Type")
results_tree.pack(padx=10, pady=10, fill="both", expand=True)

# Run Again Logic
ask_run_again_window = None # Initialize

root.mainloop()