import requests
import json
import sys

def update_settings(replication_factor, consistency_mode):
    url = "http://127.0.0.1:8000/update_settings"
    headers = {"Content-Type": "application/json"}
    data = {
        "replication_factor": replication_factor,
        "consistency_mode": consistency_mode
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        print("Settings updated successfully.")
    else:
        print(f"Failed to update settings. Status code: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python change_configurations.py <replication_factor> <consistency_mode>")
        sys.exit(1)
    
    replication_factor = int(sys.argv[1])
    consistency_mode = sys.argv[2]
    
    update_settings(replication_factor, consistency_mode)