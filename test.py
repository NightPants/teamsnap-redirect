import requests

CLIENT_ID = "Eocrv5rmAg8v33ADCmM0dFS8dE4Vw6UJ5RdtIRDPojk"
CLIENT_SECRET = "xtIrH7i_doYM4Jj-jVlDXiBjCkqTT1wMmbHQa9tzGuM"
TOKEN_URL = "https://auth.teamsnap.com/oauth/token"
USER_INFO_URL = "https://api.teamsnap.com/v3/me"

def get_access_token():
    token_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    
    response = requests.post(TOKEN_URL, data=token_data)
    
    if response.status_code == 200:
        token_info = response.json()
        access_token = token_info.get("access_token")
        
        if access_token:
            print("Access Token Retrieved Successfully!")
            return access_token
        else:
            print("Error: Access token not found in the response.")
            return None
    else:
        print(f"Error fetching token. Status Code: {response.status_code}")
        print("Response:", response.text)
        return None

def get_user_info(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.get(USER_INFO_URL, headers=headers)
    
    if response.status_code == 200:
        user_info = response.json()
        return user_info
    else:
        print(f"Error fetching user info. Status Code: {response.status_code}")
        print("Response:", response.text)
        return None

# Example Usage
access_token = get_access_token()

if access_token:
    user_info = get_user_info(access_token)
    if user_info:
        print("User Info:", user_info)
else:
    print("Failed to retrieve access token.")
