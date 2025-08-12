#!/usr/bin/env python3

import os
from datetime import datetime, timedelta
from src.slack_client import TownCrierSlackClient

def find_latest_summary():
    """Find the most recent summary file"""
    summaries_dir = "summaries"
    if not os.path.exists(summaries_dir):
        print("❌ No summaries directory found. Run summarize_all_channels.py first.")
        return None
    
    summary_files = [f for f in os.listdir(summaries_dir) if f.startswith("summary_") and f.endswith(".txt")]
    if not summary_files:
        print("❌ No summary files found in summaries directory")
        return None
    
    latest_file = sorted(summary_files)[-1]
    filepath = os.path.join(summaries_dir, latest_file)
    
    return filepath

def main():
    print("=== TownCrier Summary Poster ===\n")
    
    # Find the latest summary file
    summary_path = find_latest_summary()
    if not summary_path:
        return
    
    print(f"📂 Using summary file: {summary_path}")
    
    # Load the summary content
    with open(summary_path, 'r', encoding='utf-8') as f:
        summary_content = f.read()
    
    # Initialize Slack client
    client = TownCrierSlackClient()
    
    # Test connection
    print("Testing connection...")
    client.test_connection()
    
    # Get all channels to find daily-overview
    print("\nLooking for #daily-overview channel...")
    try:
        response = client.client.conversations_list(
            types="public_channel",
            limit=200
        )
        
        target_channel = None
        for channel in response['channels']:
            if channel['name'] == 'daily-overview':
                target_channel = channel
                break
        
        if not target_channel:
            print("❌ Could not find #daily-overview channel")
            print("Available channels:")
            for channel in response['channels']:
                print(f"  - #{channel['name']}")
            return
        
        print(f"✅ Found #{target_channel['name']} (ID: {target_channel['id']})")
        
    except Exception as e:
        print(f"❌ Failed to get channels: {str(e)}")
        return
    
    # Show preview
    print(f"\n📝 Summary preview:")
    print("-" * 50)
    print(summary_content[:500] + "..." if len(summary_content) > 500 else summary_content)
    print("-" * 50)
    
    # Confirm posting
    confirm = input(f"\nPost this summary to #{target_channel['name']}? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("Cancelled.")
        return
    
    # Post 7-day date range first
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    date_range = f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"
    print(f"\n📤 Posting date message to #{target_channel['name']}...")
    
    try:
        date_response = client.post_message(target_channel['id'], date_range)
        thread_ts = date_response.get('ts')
        print(f"✅ Date message posted successfully!")
        
        # Post the summary as a reply
        print(f"📤 Posting summary as reply...")
        summary_response = client.post_reply(target_channel['id'], thread_ts, summary_content)
        print(f"✅ Summary posted as reply successfully!")
        print(f"Thread timestamp: {thread_ts}")
        
    except Exception as e:
        print(f"❌ Failed to post messages: {str(e)}")

if __name__ == "__main__":
    main()