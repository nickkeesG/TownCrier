#!/usr/bin/env python3

import json
import os
import time
from datetime import datetime
from src.slack_client import TownCrierSlackClient

def collect_all_messages():
    print("=== TownCrier Message Collection ===\n")
    
    # Initialize client
    client = TownCrierSlackClient()
    
    # Test connection
    print("Testing connection...")
    client.test_connection()
    
    # Get all lab channels
    print("\nFinding lab-notes and surface-area channels...")
    channels = client.get_lab_channels()
    
    # Collect messages from all accessible channels
    all_data = {
        "collection_time": datetime.now().isoformat(),
        "channels": {}
    }
    
    accessible_count = 0
    inaccessible_count = 0
    total_messages = 0
    
    print(f"\nCollecting messages from {len(channels)} channels...")
    print("=" * 50)
    
    for i, channel in enumerate(channels, 1):
        channel_name = channel['name']
        channel_id = channel['id']
        
        try:
            # Progress bar
            progress = "█" * (i * 20 // len(channels)) + "░" * (20 - (i * 20 // len(channels)))
            print(f"[{progress}] {i:2d}/{len(channels)} 📥 {channel_name}...", end=" ")
            messages = client.get_channel_history(channel_id, days=7)
            
            # Process messages to extract useful info and collect threaded replies
            processed_messages = []
            thread_replies_count = 0
            
            for msg in messages:
                msg_text = msg.get('text', '')
                msg_head = msg_text[:100] + "..." if len(msg_text) > 100 else msg_text
                print(f"    📄 Message head: {repr(msg_head)}")
                
                processed_msg = {
                    "timestamp": msg.get('ts'),
                    "user": msg.get('user'),
                    "text": msg_text,
                    "type": msg.get('type'),
                    "subtype": msg.get('subtype'),
                    "thread_ts": msg.get('thread_ts'),
                    "reply_count": msg.get('reply_count', 0),
                    "replies": []
                }
                
                # Check if this message has replies (it's a thread parent)
                reply_count = msg.get('reply_count', 0)
                has_thread_ts = msg.get('thread_ts')
                
                print(f"    DEBUG: reply_count={reply_count}, thread_ts={has_thread_ts}")
                
                # Fetch replies for any message that has replies
                if reply_count > 0:
                    print(f"    FETCHING replies for parent message: {msg.get('text', '')[:50]}...")
                    # This is the parent message of a thread
                    thread_replies = client.get_thread_replies(channel_id, msg.get('ts'))
                    print(f"    Got {len(thread_replies)} replies")
                    
                    processed_replies = []
                    for reply in thread_replies:
                        reply_text = reply.get('text', '')
                        reply_head = reply_text[:100] + "..." if len(reply_text) > 100 else reply_text
                        print(f"      🧵 Reply head: {repr(reply_head)}")
                        
                        processed_reply = {
                            "timestamp": reply.get('ts'),
                            "user": reply.get('user'),
                            "text": reply_text,
                            "type": reply.get('type'),
                            "subtype": reply.get('subtype'),
                            "thread_ts": reply.get('thread_ts')
                        }
                        processed_replies.append(processed_reply)
                    
                    processed_msg["replies"] = processed_replies
                    thread_replies_count += len(processed_replies)
                
                processed_messages.append(processed_msg)
            
            all_data["channels"][channel_name] = {
                "id": channel_id,
                "message_count": len(messages),
                "thread_replies_count": thread_replies_count,
                "messages": processed_messages
            }
            
            accessible_count += 1
            total_messages += len(messages) + thread_replies_count
            
            if thread_replies_count > 0:
                print(f"✅ {len(messages)} messages + {thread_replies_count} replies")
            else:
                print(f"✅ {len(messages)} messages")
            
        except Exception as e:
            if "not_in_channel" in str(e):
                print("❌ Bot not in channel")
                all_data["channels"][channel_name] = {
                    "id": channel_id,
                    "error": "bot_not_in_channel",
                    "message_count": 0,
                    "messages": []
                }
                inaccessible_count += 1
            else:
                print(f"❌ Error: {str(e)}")
                all_data["channels"][channel_name] = {
                    "id": channel_id,
                    "error": str(e),
                    "message_count": 0,
                    "messages": []
                }
                inaccessible_count += 1
    
    print("=" * 50)
    print(f"Collection complete!")
    print(f"✅ Accessible channels: {accessible_count}")
    print(f"❌ Inaccessible channels: {inaccessible_count}")
    print(f"📊 Total messages collected: {total_messages}")
    
    # Save to file in data folder
    os.makedirs("data", exist_ok=True)
    filename = f"data/messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Data saved to: {filename}")
    
    return all_data

if __name__ == "__main__":
    collect_all_messages()