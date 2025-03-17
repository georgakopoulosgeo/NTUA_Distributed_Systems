import requests
import argparse
import json
import sys

def update_settings(replication_factor, consistency_mode, aws_flag=False):
    if aws_flag:
        url = "http://10.0.62.44:8000/update_settings"
    else:
        url = "http://127.0.0.1:8000/update_settings"
    headers = {"Content-Type": "application/json"}
    data = {
        "replication_factor": replication_factor,
        "consistency_mode": consistency_mode
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=5)
    except Exception as e:
        print(f"Failed to update settings: {e}")
        sys.exit(1)
    
    if response.status_code == 200:
        print("Settings updated successfully.")
    else:
        print(f"Failed to update settings. Status code: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Change the replication factor and consistency mode of the Chordify system.")
    parser.add_argument("--replication_factor", type=int, help="The new replication factor")
    parser.add_argument("--consistency_mode", type=str, help="The new consistency mode (eventual/linearizable)")
    parser.add_argument( "--aws", action="store_true", help="Use the AWS server instead of localhost")
    args = parser.parse_args()
    replication_factor = args.replication_factor
    consistency_mode = args.consistency_mode
    aws_flag = args.aws
    
    update_settings(replication_factor, consistency_mode, aws_flag)

# python3 change_configurations.py  --replication_factor 3 --consistency_mode linearizable --aws