#!/usr/bin/env python3

import json
import os
import re
import time
from datetime import datetime
from src.slack_client import TownCrierSlackClient

def resolve_user_mentions(text, user_cache):
    """Replace <@USER_ID> mentions with user names"""
    if not text:
        return text
    
    # Find all user mentions in the format <@USER_ID>
    user_mentions = re.findall(r'<@(U[A-Z0-9]+)>', text)
    
    for user_id in user_mentions:
        if user_id in user_cache:
            user_name = user_cache[user_id].get('display_name') or user_cache[user_id].get('real_name') or user_cache[user_id].get('name')
            if user_name and user_name != 'Unknown':
                text = text.replace(f'<@{user_id}>', f'@{user_name}')
    
    return text

def collect_all_history():
    print("=== TownCrier Complete Historical Collection ===\n")
    print("⚠️  WARNING: This will collect ALL messages from ALL accessible channels")
    print("⚠️  This may take MANY HOURS and use significant API calls")
    
    confirm = input("\nDo you want to continue? (yes/NO): ").strip().lower()
    if confirm != 'yes':
        print("Collection cancelled.")
        return
    
    # Initialize client
    client = TownCrierSlackClient()
    
    # Test connection
    print("\nTesting connection...")
    client.test_connection()
    
    # Get all accessible channels
    print("\nFinding all accessible channels...")
    channels = client.get_all_accessible_channels()
    
    # Initialize user cache for resolving user IDs to names
    user_cache = {}
    print(f"\nInitializing user cache...")
    
    # Collect messages from all accessible channels
    all_data = {
        "collection_time": datetime.now().isoformat(),
        "collection_type": "complete_history",
        "channels": {}
    }
    
    accessible_count = 0
    inaccessible_count = 0
    total_messages = 0
    
    print(f"\nCollecting ALL HISTORICAL messages from {len(channels)} channels...")
    print("=" * 70)
    
    for i, channel in enumerate(channels, 1):
        channel_name = channel['name']
        channel_id = channel['id']
        
        try:
            # Progress bar
            progress = "█" * (i * 20 // len(channels)) + "░" * (20 - (i * 20 // len(channels)))
            print(f"[{progress}] {i:2d}/{len(channels)} 📥 {channel_name}...", end=" ")
            
            # Get ALL channel history (no time limit)
            messages = get_complete_channel_history(client, channel_id)
            
            # Process messages to extract useful info and collect threaded replies
            processed_messages = []
            thread_replies_count = 0
            
            for msg in messages:
                msg_text = msg.get('text', '')
                user_id = msg.get('user')
                
                # Resolve user ID to name and cache it
                user_name = None
                if user_id and user_id not in user_cache:
                    print(f"\n    🔍 Looking up user: {user_id}")
                    user_info = client.get_user_info(user_id)
                    user_cache[user_id] = user_info
                
                if user_id and user_id in user_cache:
                    user_info = user_cache[user_id]
                    user_name = user_info.get('display_name') or user_info.get('real_name') or user_info.get('name')
                
                # Replace user mentions in message text
                resolved_text = resolve_user_mentions(msg_text, user_cache)
                
                msg_head = resolved_text[:100] + "..." if len(resolved_text) > 100 else resolved_text
                if len(msg_text) > 100:  # Only print for longer messages to reduce spam
                    print(f"\n    📄 Message head: {repr(msg_head)}")
                
                processed_msg = {
                    "timestamp": msg.get('ts'),
                    "user_id": user_id,
                    "user_name": user_name or "Unknown",
                    "text": resolved_text,
                    "type": msg.get('type'),
                    "subtype": msg.get('subtype'),
                    "thread_ts": msg.get('thread_ts'),
                    "reply_count": msg.get('reply_count', 0),
                    "replies": []
                }
                
                # Check if this message has replies (it's a thread parent)
                reply_count = msg.get('reply_count', 0)
                
                # Fetch replies for any message that has replies
                if reply_count > 0:
                    print(f"\n    FETCHING {reply_count} replies for thread...")
                    thread_replies = client.get_thread_replies(channel_id, msg.get('ts'))
                    
                    processed_replies = []
                    for reply in thread_replies:
                        reply_text = reply.get('text', '')
                        reply_user_id = reply.get('user')
                        
                        # Resolve reply user ID to name and cache it
                        reply_user_name = None
                        if reply_user_id and reply_user_id not in user_cache:
                            print(f"      🔍 Looking up reply user: {reply_user_id}")
                            user_info = client.get_user_info(reply_user_id)
                            user_cache[reply_user_id] = user_info
                        
                        if reply_user_id and reply_user_id in user_cache:
                            user_info = user_cache[reply_user_id]
                            reply_user_name = user_info.get('display_name') or user_info.get('real_name') or user_info.get('name')
                        
                        # Replace user mentions in reply text
                        resolved_reply_text = resolve_user_mentions(reply_text, user_cache)
                        
                        processed_reply = {
                            "timestamp": reply.get('ts'),
                            "user_id": reply_user_id,
                            "user_name": reply_user_name or "Unknown",
                            "text": resolved_reply_text,
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
                print(f"\n✅ {len(messages)} messages + {thread_replies_count} replies")
            else:
                print(f"\n✅ {len(messages)} messages")
            
        except Exception as e:
            if "not_in_channel" in str(e):
                print("\n❌ Bot not in channel")
                all_data["channels"][channel_name] = {
                    "id": channel_id,
                    "error": "bot_not_in_channel",
                    "message_count": 0,
                    "messages": []
                }
                inaccessible_count += 1
            else:
                print(f"\n❌ Error: {str(e)}")
                all_data["channels"][channel_name] = {
                    "id": channel_id,
                    "error": str(e),
                    "message_count": 0,
                    "messages": []
                }
                inaccessible_count += 1
    
    print("=" * 70)
    print(f"Historical collection complete!")
    print(f"✅ Accessible channels: {accessible_count}")
    print(f"❌ Inaccessible channels: {inaccessible_count}")
    print(f"📊 Total messages collected: {total_messages}")
    print(f"👥 Users resolved: {len(user_cache)}")
    
    # Add user cache to data
    all_data["user_cache"] = user_cache
    
    # Save to main folder
    filename = f"complete_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Complete history saved to: {filename}")
    
    return all_data

def get_complete_channel_history(client, channel_id):
    """Get ALL messages from a channel with no time limit"""
    try:
        print(f"\n    Fetching complete history for channel...")
        
        all_messages = []
        cursor = None
        page_count = 0
        
        while True:
            page_count += 1
            time.sleep(30)  # Rate limiting before API call
            
            # Build API call parameters
            params = {
                'channel': channel_id,
                'limit': 15  # Current Slack API limit per request
            }
            
            if cursor:
                params['cursor'] = cursor
            
            print(f"\n      Page {page_count}: requesting up to {params['limit']} messages...")
            
            # Retry logic for rate limits
            max_retries = 3
            for retry in range(max_retries):
                try:
                    response = client.client.conversations_history(**params)
                    break  # Success, exit retry loop
                except Exception as e:
                    if 'rate_limited' in str(e):
                        retry_after = 120  # Default retry time
                        print(f"\n      Rate limited, retrying in {retry_after} seconds (attempt {retry + 1}/{max_retries})...")
                        time.sleep(retry_after)
                    else:
                        raise  # Re-raise non-rate-limit errors
            else:
                # All retries exhausted
                raise Exception("Rate limit retries exhausted")
            
            page_messages = response['messages']
            all_messages.extend(page_messages)
            
            print(f"\n      Page {page_count}: got {len(page_messages)} messages (total: {len(all_messages)})")
            
            # Check if we have more pages
            if not response.get('has_more', False):
                print(f"\n      Reached end of channel history")
                break
                
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break
        
        print(f"\n    Found {len(all_messages)} total messages in channel")
        
        return all_messages
        
    except Exception as e:
        print(f"\n    ❌ Failed to get complete channel history: {str(e)}")
        raise

if __name__ == "__main__":
    collect_all_history()