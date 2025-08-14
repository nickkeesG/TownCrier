#!/usr/bin/env python3

import os
import json
import requests
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

def find_most_recent_json(data_dir="data"):
    """Find the most recently modified JSON file in the data directory."""
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory '{data_dir}' not found")
    
    json_files = list(data_path.glob("*.json"))
    if not json_files:
        raise FileNotFoundError("No JSON files found in data directory")
    
    # Sort by modification time, most recent first
    most_recent = max(json_files, key=os.path.getmtime)
    return most_recent

def find_all_json_files(data_dir="data"):
    """Find all JSON files in the data directory, sorted by modification time."""
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory '{data_dir}' not found")
    
    json_files = list(data_path.glob("*.json"))
    if not json_files:
        raise FileNotFoundError("No JSON files found in data directory")
    
    # Sort by modification time, oldest first
    json_files.sort(key=os.path.getmtime)
    return json_files

def post_json_to_slack(json_file_path, bearer_token, url="https://offers-and-asks-slack-nbgim.ondigitalocean.app/external/slack-message"):
    """Post JSON data to the Slack endpoint."""
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    headers = {
        'Authorization': f'Bearer {bearer_token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code == 200:
        print(f"Successfully posted {json_file_path.name} to Slack endpoint")
        return True
    else:
        print(f"Failed to post data. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Post JSON data to Slack endpoint')
    parser.add_argument('--all', action='store_true', help='Post all JSON files instead of just the most recent')
    args = parser.parse_args()
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Get bearer token from .env file
    bearer_token = os.getenv('BEARER_TOKEN')
    if not bearer_token:
        print("Error: BEARER_TOKEN not found in .env file")
        print("Add it to .env file: BEARER_TOKEN=your_token_here")
        return 1
    
    try:
        if args.all:
            # Find and post all JSON files
            json_files = find_all_json_files()
            print(f"Found {len(json_files)} JSON files to post")
            
            success_count = 0
            for json_file in json_files:
                print(f"\nPosting: {json_file.name}")
                if post_json_to_slack(json_file, bearer_token):
                    success_count += 1
                    
            print(f"\nCompleted: {success_count}/{len(json_files)} files posted successfully")
            return 0 if success_count == len(json_files) else 1
        else:
            # Find most recent JSON file
            most_recent_file = find_most_recent_json()
            print(f"Found most recent file: {most_recent_file}")
            
            # Post to Slack endpoint
            success = post_json_to_slack(most_recent_file, bearer_token)
            
            return 0 if success else 1
        
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())