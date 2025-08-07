#!/usr/bin/env python3

import json
import os
from src.slack_client import TownCrierSlackClient

def upload_json_to_slack():
    print("=== TownCrier JSON File Uploader ===\n")
    
    # Find the most recent JSON file
    data_dir = "data"
    json_files = [f for f in os.listdir(data_dir) if f.startswith("messages_") and f.endswith(".json")]
    if not json_files:
        print("❌ No JSON files found in data directory")
        return
    
    latest_file = sorted(json_files)[-1]
    filepath = os.path.join(data_dir, latest_file)
    
    print(f"📂 Using file: {filepath}")
    
    # Initialize Slack client
    client = TownCrierSlackClient()
    
    # Test connection
    print("Testing connection...")
    client.test_connection()
    
    # Get all channels to find slack-bot-workshop
    print("\nLooking for #slack-bot-workshop channel...")
    try:
        response = client.client.conversations_list(
            types="public_channel",
            limit=200
        )
        
        target_channel = None
        for channel in response['channels']:
            if channel['name'] == 'slack-bot-workshop':
                target_channel = channel
                break
        
        if not target_channel:
            print("❌ Could not find #slack-bot-workshop channel")
            print("Available channels:")
            for channel in response['channels']:
                print(f"  - #{channel['name']}")
            return
        
        print(f"✅ Found #{target_channel['name']} (ID: {target_channel['id']})")
        
    except Exception as e:
        print(f"❌ Failed to get channels: {str(e)}")
        return
    
    # Confirm upload
    file_size = os.path.getsize(filepath) / 1024  # KB
    print(f"\n📎 File: {latest_file} ({file_size:.1f} KB)")
    print(f"📍 Target: #{target_channel['name']}")
    
    confirm = input(f"\nUpload this JSON file to #{target_channel['name']}? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("Cancelled.")
        return
    
    # Upload the file
    print(f"\n📤 Uploading to #{target_channel['name']}...")
    try:
        response = client.upload_file(
            channel_id=target_channel['id'],
            file_path=filepath,
            filename=latest_file,
            initial_comment="Hi! I'm not ready to make summaries yet, but here's the raw data from today's lab-notes scrape 😊 If you'd like to experiment with it, be my guest!"
        )
        print(f"✅ Successfully uploaded {latest_file} to #{target_channel['name']}!")
    except Exception as e:
        print(f"❌ Failed to upload file: {str(e)}")

if __name__ == "__main__":
    upload_json_to_slack()