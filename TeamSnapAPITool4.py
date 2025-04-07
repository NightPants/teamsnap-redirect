import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.filedialog import asksaveasfilename
from urllib.parse import urlencode
from datetime import datetime, timedelta
import requests
import webbrowser
import pytz
import csv
import os
import json
from tkcalendar import Calendar
import threading
import time  # For simulating progress

# Credentials and URLs
CLIENT_ID = "Eocrv5rmAg8v33ADCmM0dFS8dE4Vw6UJ5RdtIRDPojk"
CLIENT_SECRET = "xtIrH7i_doYM4Jj-jVlDXiBjCkqTT1wMmbHQa9tzGuM"
AUTH_URL = "https://auth.teamsnap.com/oauth/authorize"
TOKEN_URL = "https://auth.teamsnap.com/oauth/token"
REDIRECT_URI = "https://www.tworiverlittleleague.com/tsapiauthenticator/"
#REDIRECT_URI = "https://github.com/NightPants/teamsnap-redirect"
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
last_refreshed_label = None
progress_bar_refresh_teams = None
#show_all_dates = tk.BooleanVar() # For showing entire schedule

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

def get_user_teams_with_details(access_token, progress_callback=None):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    team_info = {}
    try:
        response = requests.get(USER_INFO_URL, headers=headers)
        response.raise_for_status()
        user_data = response.json()

        if "collection" in user_data and "items" in user_data["collection"]:
            managed_team_ids = []
            owned_team_ids = []
            commissioned_team_ids = []
            for item in user_data["collection"]["items"]:
                for entry in item.get("data",):
                    if entry.get("name") == "managed_team_ids":
                        managed_team_ids.extend(entry.get("value", []))
                    elif entry.get("name") == "owned_team_ids":
                        owned_team_ids.extend(entry.get("value", []))
                    elif entry.get("name") == "commissioned_team_ids":
                        commissioned_team_ids.extend(entry.get("value", []))

            all_team_ids = list(set(managed_team_ids + owned_team_ids + commissioned_team_ids))
            total_teams = len(all_team_ids)
            teams_processed = 0

            # Fetch team details
            for team_id in all_team_ids:
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
                teams_processed += 1
                if progress_callback:
                    progress_callback(teams_processed, total_teams)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user teams: {e}")
    return team_info

def authenticate():
    auth_url = get_authorization_url()
    webbrowser.open(auth_url)
    auth_button.pack_forget() # Hide the authenticate button
    #auth_code_frame.pack(pady=10) # Show the authentication code input frame
    auth_code_entry.config(state=tk.NORMAL) # Enable the entry
    submit_auth_code_button.config(state=tk.NORMAL) # Enable the button

def submit_auth_code():
    global access_token, teams, auth_status_label, stored_team_info
    code = auth_code_entry.get()
    access_token = get_access_token(code)
    if access_token:
        auth_status_label.config(text="Authentication Status: Authenticated", foreground="green")
        # Removed the success messagebox
        auth_code_frame.pack_forget() # Hide the input fields
        # Load team info based on selection after successful auth
        if team_info_choice.get() == "existing":
            global stored_team_info, teams, team_options_list
            stored_team_info = load_team_info_from_csv()
            if stored_team_info:
                teams = stored_team_info
                team_options_list = sorted([(details['name'], details['division'], team_id) for team_id, details in teams.items()], key=lambda item: item[0])
                #print(f"Data fetched from get_user_teams_with_details: {stored_team_info}")
                populate_team_picker(stored_team_info)
                # Removed the "using existing" messagebox
            else:
                messagebox.showinfo("Info", "No stored team information found. Please refresh teams.")
        elif team_info_choice.get() == "refresh":
            # Do nothing here, the "Refresh Now" button will handle it
            pass
        else:
            auth_status_label.config(text="Authentication Status: Failed", foreground="red")
            messagebox.showerror("Error", "Failed to retrieve access token.")

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

def get_last_modified_time():
    """Returns the last modified timestamp of the team info CSV file."""
    if os.path.exists(TEAM_INFO_CSV_FILE):
        timestamp = os.path.getmtime(TEAM_INFO_CSV_FILE)
        dt_object = datetime.fromtimestamp(timestamp, tz=LOCAL_TIMEZONE)
        return dt_object.strftime("%m/%d/%y %I:%M %p")
    return "N/A"

def copy_table_to_clipboard(event):
    selected_items = results_tree.selection()
    if not selected_items:
        messagebox.showinfo("Info", "No rows selected to copy.")
        return

    clipboard_text = ""
    for item_id in selected_items:
        values = results_tree.item(item_id, 'values')
        clipboard_text += "\t".join(values) + "\n"

    root.clipboard_clear()
    root.clipboard_append(clipboard_text)
    root.update()
    messagebox.showinfo("Info", "Selected row(s) copied to clipboard.")

def update_progress_bar_refresh(current, total):
    global progress_bar_refresh_teams
    if progress_bar_refresh_teams:
        progress_bar_refresh_teams['value'] = current
        progress_bar_refresh_teams['maximum'] = total
        root.update_idletasks()

def refresh_teams_now():
    global access_token, teams, refresh_now_button, team_info_frame, last_refreshed_label, progress_bar_refresh_teams, team_options_list
    if not access_token:
        messagebox.showerror("Error", "Please authenticate first.")
        return

    if refresh_now_button:
        refresh_now_button.config(state=tk.DISABLED)
        progress_bar_refresh_teams = ttk.Progressbar(team_info_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        progress_bar_refresh_teams.pack(side=tk.LEFT, padx=5)

    def fetch_and_update():
        global teams, team_options_list
        try:
            teams = get_user_teams_with_details(access_token, progress_callback=update_progress_bar_refresh)
            if teams:
                save_team_info_to_csv(teams)
                team_options_list = sorted([(details['name'], details['division'], team_id) for team_id, details in teams.items()], key=lambda item: item[0])
                root.after(0, populate_team_picker(teams)) # Populate picker on the main thread
                if last_refreshed_label:
                    last_refreshed_label.config(text=f"Last Refreshed: {get_last_modified_time()}")
            else:
                messagebox.showerror("Error", "Could not retrieve team information.")
        finally:
            if progress_bar_refresh_teams:
                progress_bar_refresh_teams.stop()
                progress_bar_refresh_teams.destroy()
                # progress_bar_refresh_teams = None
            if refresh_now_button:
                refresh_now_button.config(state=tk.NORMAL)

    threading.Thread(target=fetch_and_update).start()

def populate_team_picker(teams_data):
    global teams, team_options_list
    teams = teams_data
    team_options_list = []
    unique_divisions = set()
    team_options_list.append(("All Teams", "all")) # Add "All Teams" option

    for team_id, team_info in teams.items():
        team_name = team_info.get("name", "Unknown Team")
        division = team_info.get("division", "Unknown Division")
        team_options_list.append((f"{team_name} ({division})", team_id))
        unique_divisions.add(division)

    # Sort the team_options_list alphabetically by team name
    team_options_list.sort(key=lambda item: item[0])

    team_options = [option[0] for option in team_options_list]
    team_picker['values'] = team_options
    team_picker.set("All Teams") # Set the default value to "All Teams"     
    team_id_var.set("all") # Immediately set team_id_var to "all" since "All Teams" is the default

    # Populate division options
    division_options = ["All Divisions"] + sorted(list(unique_divisions))
    division_combo['values'] = division_options
    division_combo.set("All Divisions")

def on_division_selected(event):
    selected_division = division_var.get()
    team_name_var.set("All Teams in Division") # Optionally update team picker
    team_id_var.set("division_filter") # Set a special value to identify division filtering
    print(f"Selected Division: {selected_division}")

def on_team_selected(event):
    selected_team = team_picker.get()
    for name, team_id in team_options_list:
        if name == selected_team:
            team_id_var.set(team_id)
            # Optionally, extract and set team_division_var if needed
            print(f"Selected Team ID: {team_id}")
            return
    team_id_var.set("all") # If "All Teams" is selected

def team_info_choice_changed():
    global refresh_now_button, last_refreshed_label, progress_bar_refresh_teams
    if team_info_choice.get() == "refresh":
        if refresh_now_button is None:
            refresh_now_button = ttk.Button(team_info_frame, text="Refresh Now", command=refresh_teams_now)
            refresh_now_button.pack(side=tk.LEFT, padx=5, pady=5)
        elif refresh_now_button.winfo_ismapped() == 0:
            refresh_now_button.pack(side=tk.LEFT, padx=5, pady=5)
    else:
        if refresh_now_button is not None and refresh_now_button.winfo_ismapped() == 1:
            refresh_now_button.pack_forget()
            if last_refreshed_label:
                last_refreshed_label.pack_forget()
            if progress_bar_refresh_teams:  # Add this check
                progress_bar_refresh_teams = None
                progress_bar_refresh_teams.stop()
                progress_bar_refresh_teams.destroy()

def update_progress_bar(current, total):
    global progress_bar
    if progress_bar:
        progress_bar['value'] = current
        progress_bar['maximum'] = total
        root.update_idletasks()

def fetch_events_threaded():
    global access_token, teams, events_data, cal, results_tree, export_button, progress_bar, fetch_button,event_type_var

    selected_date = cal.get_date()
    target_date = datetime.strptime(selected_date, "%m/%d/%y").strftime("%m/%d/%y")  # Format to MM/DD/YY

    event_type = event_type_var.get()
    event_type_str = ""
    if event_type == 'Games':
        event_type_str = "Games"
    elif event_type == 'Practices':
        event_type_str = "Practices"
    elif event_type == 'Games w/ Ump':
        event_type_str = "Games" # We'll filter by division later
    else:
        event_type_str = "All"

    selected_town = town_var.get()
    selected_team_id = team_id_var.get()
    selected_division = division_var.get()
    
    if event_type == 'Games w/ Ump':
        ump_divisions = {
            "4th / 5th Grade Softball 2025",
            "6th / 7th / 8th Grade Softball 2025",
            "Juniors BB 2025 (13/14U)",
            "Majors BB 2025 (11/12U)",
            "Minors BB 2025 (10U)",
            "Rookies BB 2025 (9U)"
        }
        all_fetched_events = []
        seen_events = set()
        teams_to_fetch = {team_id: info for team_id, info in teams.items() if info.get('division') in ump_divisions}
        total_teams_to_fetch = len(teams_to_fetch)
        teams_fetched = 0
        for team_id, team_info in teams_to_fetch.items():
            events = get_events_by_date(access_token, team_id, target_date, event_type_str)
            division = team_info.get('division', 'Unknown Division')
            team_name = team_info.get('name', 'Unknown Team')
            for event in events:
                opponent = event.get('opponent', 'N/A')
                is_game = event.get('is_game')
                if is_game:
                    teams_in_game = tuple(sorted((team_name, opponent)))
                    event_identifier = (event.get('date'), event.get('time'), event.get('location'), teams_in_game, division, "Game")
                else:
                    event_identifier = (event.get('date'), event.get('time'), event.get('location'), team_name, opponent, division, "Practice")

                if event_identifier not in seen_events:
                    event['division'] = division
                    event['team_name'] = team_name
                    all_fetched_events.append(event)
                    seen_events.add(event_identifier)
            teams_fetched += 1
            root.after(0, update_progress_bar, teams_fetched, total_teams_to_fetch)
        events_data = all_fetched_events
    elif selected_division != "All Divisions" and selected_team_id == "division_filter":
        all_fetched_events = []
        seen_events = set()  # Initialize a set to track seen events
        total_teams_to_fetch = sum(1 for team_info in teams.values() if team_info.get('division') == selected_division)
        teams_fetched = 0
        for team_id, team_info in teams.items():
            if team_info.get('division') == selected_division:
                events = get_events_by_date(access_token, team_id, target_date, event_type_str)
                division = team_info.get('division', 'Unknown Division')
                team_name = team_info.get('name', 'Unknown Team')  # Get the team name here
                for event in events:
                    opponent = event.get('opponent', 'N/A')
                    is_game = event.get('is_game')
                    if is_game:
                        teams_in_game = tuple(sorted((team_name, opponent)))
                        event_identifier = (event.get('date'), event.get('time'), event.get('location'), teams_in_game, division, "Game")
                    else:
                        event_identifier = (event.get('date'), event.get('time'), event.get('location'), team_name, opponent, division, "Practice")

                    if event_identifier not in seen_events:
                        event['division'] = division
                        event['team_name'] = team_name  # Add the actual team name to the event data
                        all_fetched_events.append(event)
                        seen_events.add(event_identifier)
                teams_fetched += 1
                root.after(0, update_progress_bar, teams_fetched, total_teams_to_fetch)
        events_data = all_fetched_events
    elif selected_team_id == "all":
        all_fetched_events = []
        seen_events = set()  # Initialize a set to track seen events
        total_teams_to_fetch = len(teams)
        teams_fetched = 0
        for team_id in teams:
            events = get_events_by_date(access_token, team_id, target_date, event_type_str)
            division = teams.get(team_id, {}).get('division', 'Unknown Division')
            team_info = teams.get(team_id, {})
            team_name = team_info.get('name', 'Unknown Team')
            for event in events:
                opponent = event.get('opponent', 'N/A')
                is_game = event.get('is_game')
                if is_game:
                    teams_in_game = tuple(sorted((team_name, opponent)))
                    event_identifier = (event.get('date'), event.get('time'), event.get('location'), teams_in_game, division, "Game")
                else:
                    event_identifier = (event.get('date'), event.get('time'), event.get('location'), team_name, opponent, division, "Practice")

                if event_identifier not in seen_events:
                    event['division'] = division
                    event['team_name'] = team_name
                    all_fetched_events.append(event)
                    seen_events.add(event_identifier)
            teams_fetched += 1
            root.after(0, update_progress_bar, teams_fetched, total_teams_to_fetch)  # Basic progress for all teams
        events_data = all_fetched_events
    elif selected_team_id and selected_team_id != "division_filter":
        params = {"team_id": selected_team_id}
        if event_type.lower() == "games":
            params["is_game"] = "true"
        elif event_type.lower() == "practices":
            params["is_game"] = "false"

        if show_all_dates.get():
            start_date = datetime(2020, 1, 1).strftime("%Y-%m-%d")
            end_date = datetime(2030, 12, 31).strftime("%Y-%m-%d")
            params["started_after"] = start_date
            params["started_before"] = end_date
            all_team_events = get_events_by_date_range(access_token, params)  # Assuming you have this function
            division = teams.get(selected_team_id, {}).get('division', 'Unknown Division')
            for event in all_team_events:
                event['division'] = division
            events_data = all_team_events
        else:
            events = get_events_by_date(access_token, selected_team_id, target_date, event_type_str, progress_callback=update_progress_bar)
            division = teams.get(selected_team_id, {}).get('division', 'Unknown Division')
            for event in events:
                event['division'] = division
            events_data = events  # Store for potential export
    else:
        root.after(0, lambda: messagebox.showerror("Error", "Please select a team."))
        root.after(0, finalize_fetch_events)
        return

    try:
        if not show_all_dates.get():
            datetime.strptime(target_date, "%m/%d/%y")

        if selected_town != "No Filter":
            events_data = filter_games_by_town(events_data, selected_town)

        root.after(0, populate_results_table, events_data, event_type_str)  # Pass event_type_str

    except ValueError as e:
        root.after(0, lambda: messagebox.showerror("Error", f"Invalid date format: {e}"))
    finally:
        root.after(0, finalize_fetch_events)

def get_events_by_date_range(access_token, params):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    all_events = []
    seen_events = set()

    try:
        response = requests.get(EVENTS_URL, headers=headers, params=params)
        response.raise_for_status()
        events_data = response.json()

        if "collection" in events_data and "items" in events_data["collection"]:
            for item in events_data["collection"]["items"]:
                event_id = None
                is_game_flag = False
                event_details = {}
                time_zone_str = None
                for entry in item.get("data",):
                    event_details[entry["name"]] = entry["value"]
                    if entry["name"] == "is_game":
                        is_game_flag = entry["value"]
                    elif entry["name"] == "id":
                        event_id = entry["value"]
                    elif entry["name"] == "time_zone":
                        time_zone_str = entry["value"]

                include_event = False
                if event_type_var.get().lower() == "games" and is_game_flag:
                    include_event = True
                elif event_type_var.get().lower() == "practices" and not is_game_flag:
                    include_event = True
                elif event_type_var.get().lower() == "all":
                    include_event = True

                if include_event:
                    try:
                        start_time_str = event_details.get("start_date")
                        location = event_details.get("location_name", "No Location")
                        opponent = event_details.get("opponent_name", "N/A")
                        division = None # Division will be populated later

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

                            event_identifier = (local_time, location, division, team_name_var.get() if not is_game_flag else tuple(sorted((team_name_var.get(), opponent))))

                            if event_identifier not in seen_events:
                                all_events.append({
                                    "full_item": item,
                                    "id": event_id,
                                    "day": local_day_str_display,
                                    "date": local_date_str_display,
                                    "time": local_time_str_display,
                                    "location": location,
                                    "division": division,
                                    "team_name": team_name_var.get(),
                                    "opponent": opponent if is_game_flag else "N/A",
                                    "start_datetime": local_time,
                                    "game_type_code": event_details.get("game_type_code", "N/A"),
                                    "is_canceled": event_details.get("is_canceled", "N/A"),
                                    "is_game": is_game_flag,
                                    "is_league_controlled": event_details.get("is_league_controlled", "")
                                })
                                seen_events.add(event_identifier)
                    except ValueError:
                        pass
    except requests.exceptions.RequestException as e:
        print(f"Error fetching events for team {params.get('team_id')}: {e}")

    all_events.sort(key=lambda x: x["start_datetime"])
    return all_events

def populate_results_table(events, event_type_str):
    global results_tree, export_button, results_label
    # Clear previous results from the table
    for item in results_tree.get_children():
        results_tree.delete(item)

    # Add a new column for "Cancelled" if it doesn't exist (only the heading needs to be set here if it wasn't initially)
    if "Cancelled" not in results_tree['columns']:
        results_tree['columns'] = ("Time", "Location", "Team", "Opponent", "Division", "Type", "Cancelled")
        results_tree.heading("Cancelled", text="Cancelled", command=lambda: sort_treeview(results_tree, "Cancelled", False))
        # Note: Do NOT set width here if you want user adjustments to persist

    if events:
        for event in events:
            is_canceled = event.get('is_canceled')
            cancelled_status = "Y" if is_canceled else ""
            tags = ('cancelled',) if is_canceled else ()  # Add a tag for cancelled events

            values = [
                event['time'],
                event['location'],
                event['team_name'],
                event.get('opponent', 'N/A') if event['is_game'] else "N/A",
                event['division'],
                "Game" if event['is_game'] else "Practice",
                cancelled_status
            ]
            results_tree.insert("", tk.END, values=tuple(values), tags=tags)

        # Configure a tag to highlight cancelled rows
        results_tree.tag_configure('cancelled', background='lightgray') # You can choose a different color

        # Show the export button if results are present
        if export_button is None:
            export_button = ttk.Button(button_frame, text="Export to CSV", command=export_events_to_csv)
            export_button.pack(side=tk.LEFT, padx=5)
        elif export_button.winfo_ismapped() == 0: # Check if not already visible
            export_button.pack(side=tk.LEFT, padx=5)

        # Update the results label with the event count
        results_label.config(text=f"Event Results: ({len(events)} events)")

    else:
        results_label.config(text="Event Results: (0 events)")
        messagebox.showinfo("Info", f"No {event_type_str.lower()} found for the selected criteria.") # Now event_type_str is defined
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
    global fetch_button, progress_bar, access_token, teams, team_id_var
    if not access_token:
        messagebox.showerror("Error", "Please authenticate first.")
        return
    if teams is None:
        messagebox.showerror("Error", "Please select an option for team information.")
        return
    if team_id_var.get() == "" and team_picker.get() != "All Teams":
        messagebox.showerror("Error", "Please select a team from the picker.")
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
                fieldnames = ['Date', 'Time', 'Location', 'Team Name', 'Opponent', 'Division', 'Event Type', 'Game Type Code', 'Is Canceled', 'League Controlled']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for event in events_data:
                    writer.writerow({
                        'Date': event['date'],
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
    global cal, export_button, refresh_now_button, progress_bar, fetch_button, results_label, team_picker, show_all_dates
    cal.set_date(datetime.now().date()) # Reset to current date
    event_type_var.set("All")
    town_var.set("No Filter")
    show_all_dates.set(False) # Reset the show all dates checkbox
    if team_picker:
        team_picker.set("All Teams")
        team_id_var.set("")
        team_division_var.set("")
        team_name_var.set("")
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
    results_label.config(text="Event Results:") # Reset the label
    ask_run_again_window.destroy()

def get_events_by_date(access_token, team_id, target_date, event_type, progress_callback=None):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    all_events = []
    seen_events = set()  # To keep track of unique events

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
                        opponent = event_details.get("opponent_name", "N/A")
                        current_team_name = None
                        # Need to find the team name associated with this event.
                        # We don't have the 'teams' dictionary here directly.
                        # The team name will be populated later in populate_results_table
                        division = None # Division will also be populated later

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

                            if show_all_dates.get() or local_date_str_display == target_date:
                                if is_game_flag:
                                    # Create a sorted tuple of team and opponent to handle reversals
                                    teams_involved = tuple(sorted((team_name_var.get(), opponent))) # Using the selected team name
                                    event_identifier = (local_time, location, division, teams_involved)
                                else:
                                    event_identifier = (local_time, location, division, team_name_var.get()) # Using the selected team name

                                if event_identifier not in seen_events:
                                    all_events.append({
                                        "full_item": item,  # Store the entire item
                                        "id": event_id, # Still store the ID
                                        "day": local_day_str_display,
                                        "date": local_date_str_display,
                                        "time": local_time_str_display,
                                        "location": location,
                                        "division": division,
                                        "team_name": team_name_var.get(), # Using the selected team name
                                        "opponent": opponent if is_game_flag else "N/A",
                                        "start_datetime": local_time,
                                        "game_type_code": event_details.get("game_type_code", "N/A"),
                                        "is_canceled": event_details.get("is_canceled", "N/A"),
                                        "is_game": is_game_flag,
                                        "is_league_controlled": event_details.get("is_league_controlled", "")
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
    elif selected_town.lower() == 'non-trll towns':
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

def update_treeview(tree, data):
    tree.delete(*tree.get_children())
    for item in data:
        tree.insert("", tk.END, values=item)

def sort_treeview(tree, col, reverse):
    """Sort the treeview based on the column header."""
    data = [(tree.set(child, col), child) for child in tree.get_children('')]
    # Sort based on the data in the specified column
    data.sort(reverse=reverse)

    for index, (val, child) in enumerate(data):
        tree.move(child, '', index)

    # Switch the sort direction for the next click
    tree.heading(col, command=lambda _col=col: sort_treeview(tree, _col, not reverse))
def heading_clicked(event):
    """Handle the click on a treeview header."""
    if results_tree.identify_region(event.x, event.y) == 'heading':
        column_id = results_tree.identify_column(event.x)
        # Get the current sort state (default to False if not set)
        current_sort = results_tree.heading(column_id).get('sort', False)
        sort_treeview(results_tree, column_id, current_sort)
        # Toggle the sort state
        results_tree.heading(column_id, sort=not current_sort)


# --- Main Window Setup ---
root = tk.Tk()
root.title("Teamsnap Event Viewer")

# --- Variables ---
# Variables to store user selections and data
team_name_var = tk.StringVar()
team_division_var = tk.StringVar()
team_id_var = tk.StringVar()
team_options_list = []
event_type_var = tk.StringVar(value="All")
town_var = tk.StringVar(value="No Filter")
team_info_choice = tk.StringVar(value="existing") # Default to use existing
show_all_dates = tk.BooleanVar()
refresh_now_button = None # Initialize

# --- Authentication Section ---
auth_status_label = ttk.Label(root, text="Authentication Status: Not Authenticated", foreground="red")
auth_status_label.pack(pady=5)

auth_button = ttk.Button(root, text="Authenticate with Teamsnap", command=authenticate)
auth_button.pack(pady=10)

# Authentication Code Input Frame (initially hidden)
auth_code_frame = ttk.LabelFrame(root, text="Enter Authorization Code")
auth_code_entry = ttk.Entry(auth_code_frame, state=tk.DISABLED)
auth_code_entry.pack(padx=10, pady=5)
submit_auth_code_button = ttk.Button(auth_code_frame, text="Submit Code", command=submit_auth_code, state=tk.DISABLED)
submit_auth_code_button.pack(pady=5)
auth_code_frame.pack(pady=10)
# auth_code_frame.pack_forget() # Initially hidden

# --- Team Information Handling Section ---
team_info_frame = ttk.LabelFrame(root, text="Team Information")
team_info_frame.pack(padx=10, pady=10, fill="x")

team_info_choice = tk.StringVar(value="existing") # Initialize with a default value

team_info_choice.trace_add("write", lambda *args: team_info_choice_changed()) # Trace changes to the radio buttons

use_existing_radio = ttk.Radiobutton(team_info_frame, text="Use Existing Team Info", variable=team_info_choice, value="existing")
use_existing_radio.pack(side=tk.LEFT, padx=5, pady=2)

refresh_teams_radio = ttk.Radiobutton(team_info_frame, text="Refresh Teams", variable=team_info_choice, value="refresh")
refresh_teams_radio.pack(side=tk.LEFT, padx=5, pady=2)

# Progress bar for refresh teams (initially hidden)
progress_bar_refresh_teams = None

refresh_now_button = ttk.Button(team_info_frame, text="Refresh Now", command=refresh_teams_now)
refresh_now_button.pack(side=tk.LEFT, padx=5, pady=5)

last_refreshed_label = ttk.Label(team_info_frame, text=f"Last Refreshed: {get_last_modified_time()}")
last_refreshed_label.pack(side=tk.LEFT, padx=15, pady=2)

# --- Container Frame for Team Selection, Division, and Town Filters ---
filter_container_frame = ttk.Frame(root)
filter_container_frame.pack(padx=10, pady=10, fill="x")

# --- Team Selection Section ---
team_selection_frame = ttk.LabelFrame(filter_container_frame, text="Select Team")
team_selection_frame.pack(side=tk.LEFT, padx=10, pady=10, fill="x", expand=True) # Use side=LEFT and expand

# Team Picker (Combobox will be populated after authentication and team info loading)
team_picker = ttk.Combobox(team_selection_frame, textvariable=team_name_var, values=[], state="readonly", width=60) # Increased width
team_picker.set("Select Team")
team_picker.pack(padx=5, pady=5)
team_picker.bind("<<ComboboxSelected>>", on_team_selected)

# --- Division Filter Section ---
division_selection_frame = ttk.LabelFrame(filter_container_frame, text="Filter by Division")
division_selection_frame.pack(side=tk.LEFT, padx=10, pady=10, fill="x", expand=True) # Use side=LEFT and expand

division_var = tk.StringVar(value="All Divisions")
division_options = ["All Divisions"]
division_combo = ttk.Combobox(division_selection_frame, textvariable=division_var, values=division_options, state="readonly", width=60)
division_combo.pack(padx=5, pady=5)
division_combo.bind("<<ComboboxSelected>>", on_division_selected)

# --- Town Filter Section ---
town_frame = ttk.LabelFrame(filter_container_frame, text="Filter by Town")
town_frame.pack(side=tk.LEFT, padx=10, pady=10, fill="x", expand=True) # Use side=LEFT and expand

town_options = ["No Filter", "Rumson", "Little Silver", "Red Bank", "Fair Haven", "Shrewsbury", "Non-TRLL Towns"]
town_combo = ttk.Combobox(town_frame, textvariable=town_var, values=town_options)
town_combo.pack(padx=5, pady=5)

# --- Date Selection Section ---
date_frame = ttk.LabelFrame(root, text="Select Date")
date_frame.pack(padx=10, pady=10, fill="x")

cal = Calendar(date_frame, selectmode='day',
                year=datetime.now().year,
                month=datetime.now().month,
                day=datetime.now().day)
cal.pack(pady=5)

# Show All Dates Checkbutton
show_all_dates = tk.BooleanVar() # For showing entire schedule
show_all_dates_check = ttk.Checkbutton(date_frame, text="Show All Dates", variable=show_all_dates)
show_all_dates_check.pack(pady=5)

# --- Event Type Filter Section ---
event_type_frame = ttk.LabelFrame(root, text="Filter by Event Type")
event_type_frame.pack(padx=10, pady=10, fill="x")

ttk.Radiobutton(event_type_frame, text="All", variable=event_type_var, value="All").pack(side=tk.LEFT, padx=5)
ttk.Radiobutton(event_type_frame, text="Games", variable=event_type_var, value="Games").pack(side=tk.LEFT, padx=5)
ttk.Radiobutton(event_type_frame, text="Practices", variable=event_type_var, value="Practices").pack(side=tk.LEFT, padx=5)
ttk.Radiobutton(event_type_frame, text="Games w/ Ump", variable=event_type_var, value="Games w/ Ump").pack(side=tk.LEFT, padx=5) # Added new option

# --- Buttons Section ---
button_frame = ttk.Frame(root)
button_frame.pack(pady=10)

fetch_button = ttk.Button(button_frame, text="Fetch Events", command=fetch_events)
fetch_button.pack(side=tk.LEFT, padx=5)

# --- Results Display Section ---
results_label = ttk.Label(root, text="Event Results:")
results_label.pack()
results_tree = ttk.Treeview(root, columns=("Time", "Location", "Team", "Opponent", "Division", "Type", "Cancelled"), show="headings", selectmode="extended") # Include "Cancelled" initially

results_tree.heading("Time", text="Time", command=lambda: sort_treeview(results_tree, "Time", False))
results_tree.heading("Location", text="Location", command=lambda: sort_treeview(results_tree, "Location", False))
results_tree.heading("Team", text="Team", command=lambda: sort_treeview(results_tree, "Team", False))
results_tree.heading("Opponent", text="Opponent", command=lambda: sort_treeview(results_tree, "Opponent", False))
results_tree.heading("Division", text="Division", command=lambda: sort_treeview(results_tree, "Division", False))
results_tree.heading("Type", text="Type", command=lambda: sort_treeview(results_tree, "Type", False))
results_tree.heading("Cancelled", text="Cancelled", command=lambda: sort_treeview(results_tree, "Cancelled", False))

results_tree.column("Time", width=40)
results_tree.column("Location", width=150)  # Set your desired width
results_tree.column("Team", width=120)    # Set your desired width
results_tree.column("Opponent", width=120) # Set your desired width
results_tree.column("Division", width=160) # Set your desired width
results_tree.column("Type", width=40)
results_tree.column("Cancelled", width=60)

results_tree.pack(padx=10, pady=10, fill="both", expand=True)

# Bind Ctrl+C to the treeview for copying
results_tree.bind("<Control-c>", copy_table_to_clipboard)

# --- Run Again Logic ---
ask_run_again_window = None # Initialize

# --- Initial Setup ---
if team_info_choice.get() == "existing":
    pass # Time will be shown on startup
elif team_info_choice.get() == "refresh":
    if refresh_now_button:
        pass # Time will be shown after refresh

# Call team_info_choice_changed once at the end of setup to handle initial state
team_info_choice_changed()

# --- Start the Tkinter Event Loop ---
root.mainloop()