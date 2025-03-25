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
    """
    Generates the TeamSnap OAuth authorization URL.

    Returns:
        str: The full authorization URL.
    """
    auth_params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "read write",  # Adjust as needed
    }
    auth_url = f"{AUTH_URL}?{requests.compat.urlencode(auth_params)}"
    return auth_url

# Step 2: Get Authorization Code
def get_authorization_code():
    """
    Directs the user to the authorization URL and asks for the authorization code.

    Returns:
        str: The authorization code entered by the user.
    """
    auth_url = get_authorization_url()
    print("Visit the following URL to authorize the app:")
    print(auth_url)
    webbrowser.open(auth_url)
    return input("Enter the authorization code: ").strip()

# Step 3: Exchange Authorization Code for Access Token
def get_access_token(authorization_code):
    """
    Exchanges the authorization code for an access token.

    Args:
        authorization_code (str): The authorization code received from the user.

    Returns:
        str: The access token if successful, None otherwise.
    """
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

# Step 4: Fetch User Info (Handles Collection+JSON)
def get_user_info(access_token):
    """
    Retrieves authenticated user information from TeamSnap.

    Args:
        access_token (str): The access token retrieved from the authorization code.

    Returns:
        dict: Parsed user information if successful, None otherwise.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(USER_INFO_URL, headers=headers)

    if response.status_code == 200:
        user_data = response.json()
        return parse_collection_json(user_data)
    else:
        print(f"Error fetching user info. Status: {response.status_code}\n{response.text}")
        return None

# Step 5: Fetch Events for Managed Division
def get_division_events(access_token):
    """
    Retrieves events for a given managed division.

    Args:
        access_token (str): The access token retrieved from authentication.

    Returns:
        list: List of event details if successful, None otherwise.
    """
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(EVENTS_URL, headers=headers)

    if response.status_code == 200:
        events_data = response.json()
        return parse_collection_json_list(events_data)
    else:
        print(f"Error fetching events. Status: {response.status_code}\n{response.text}")
        return None

# Utility: Parse Collection+JSON Format for a Single Item
def parse_collection_json(data):
    """
    Parses a Collection+JSON response and extracts relevant user details.

    Args:
        data (dict): The raw Collection+JSON response.

    Returns:
        dict: Extracted data in key-value format.
    """
    parsed_data = {}
    items = data.get("collection", {}).get("items", [])

    if not items:
        print("No items found in response.")
        return None

    for item in items:
        for entry in item.get("data", []):
            parsed_data[entry["name"]] = entry["value"]

    return parsed_data

# Utility: Parse Collection+JSON Format for a List of Items
def parse_collection_json_list(data):
    """
    Parses a Collection+JSON response and extracts a list of relevant details.

    Args:
        data (dict): The raw Collection+JSON response.

    Returns:
        list: List of extracted event details.
    """
    parsed_list = []
    items = data.get("collection", {}).get("items", [])

    if not items:
        print("No events found.")
        return None

    for item in items:
        event_details = {}
        for entry in item.get("data", []):
            event_details[entry["name"]] = entry["value"]
        parsed_list.append(event_details)

    return parsed_list

# Example Usage
def main():
    """
    Main function to run the authentication, fetch user info, and retrieve division events.
    """
    try:
        authorization_code = get_authorization_code()
        access_token = get_access_token(authorization_code)

        if access_token:
            print(f"Access Token: {access_token}")

            # Fetch user information
            user_info = get_user_info(access_token)
            if user_info:
                print("\nUser Information:")
                for key, value in user_info.items():
                    print(f"  {key}: {value}")

            # Get division events
            events = get_division_events(access_token)
            
            if events:
                print("\nEvents in Managed Division:")
                for event in events:
                    print("-" * 30)
                    for key, value in event.items():
                        print(f"{key}: {value}")
            else:
                print("No events found or failed to retrieve events.")

        else:
            print("Failed to retrieve access token.")

    except Exception as e:
        print("An error occurred:", str(e))

# Run the script
if __name__ == "__main__":
    main()
