#!/usr/bin/env python3

from src.slack_client import TownCrierSlackClient

def main():
    print("=== Testing TownCrier Slack Client ===\n")
    
    # Initialize client
    client = TownCrierSlackClient()
    
    # Test connection
    print("\n1. Testing connection...")
    client.test_connection()
    
    # Get lab channels
    print("\n2. Finding lab-notes and surface-area channels...")
    channels = client.get_lab_channels()
    
    # Test getting history from each channel to find which one the bot is in
    if channels:
        print(f"\n3. Testing which channels the bot can access...")
        for channel in channels:
            try:
                messages = client.get_channel_history(channel['id'], days=7)
                print(f"✅ Bot has access to: {channel['name']} ({len(messages)} messages)")
                if messages:
                    print(f"   Latest message preview: {messages[0].get('text', 'No text')[:50]}...")
                break  # Stop after finding the first accessible channel
            except Exception as e:
                if "not_in_channel" in str(e):
                    print(f"❌ Bot not in: {channel['name']}")
                else:
                    print(f"❌ Error accessing {channel['name']}: {str(e)}")
    else:
        print("\n3. No lab channels found to test message history")

if __name__ == "__main__":
    main()