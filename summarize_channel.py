#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import anthropic

def load_prompt():
    """Load the summarization prompt from file"""
    try:
        with open('summarization_prompt.txt', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print("❌ summarization_prompt.txt not found")
        return None

def prepare_channel_context(channel_data):
    """
    Prepare context for a single channel with messages in chronological order
    and replies attached to their parent messages
    """
    messages = channel_data.get('messages', [])
    if not messages:
        return "No messages found in this channel."
    
    # Sort messages chronologically by timestamp
    sorted_messages = sorted(messages, key=lambda x: float(x.get('timestamp', 0)))
    
    context_parts = []
    
    for msg in sorted_messages:
        # Skip messages without text
        if not msg.get('text', '').strip():
            continue
            
        # Format timestamp for readability
        ts = float(msg.get('timestamp', 0))
        dt = datetime.fromtimestamp(ts)
        timestamp_str = dt.strftime('%Y-%m-%d %H:%M')
        
        # Main message
        user_name = msg.get('user_name', 'Unknown')
        text = msg.get('text', '').strip()
        
        context_parts.append(f"[{timestamp_str}] {user_name}: {text}")
        
        # Add replies if they exist
        replies = msg.get('replies', [])
        if replies:
            # Sort replies chronologically too
            sorted_replies = sorted(replies, key=lambda x: float(x.get('timestamp', 0)))
            
            for reply in sorted_replies:
                if not reply.get('text', '').strip():
                    continue
                    
                reply_ts = float(reply.get('timestamp', 0))
                reply_dt = datetime.fromtimestamp(reply_ts)
                reply_timestamp_str = reply_dt.strftime('%Y-%m-%d %H:%M')
                reply_user = reply.get('user_name', 'Unknown')
                reply_text = reply.get('text', '').strip()
                
                context_parts.append(f"  └─ [{reply_timestamp_str}] {reply_user}: {reply_text}")
        
        # Add spacing between message threads
        context_parts.append("")
    
    return "\n".join(context_parts)

def summarize_channel_with_claude(prompt, context):
    """Send the prompt and context to Claude for summarization"""
    load_dotenv()
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key or api_key == 'your_anthropic_api_key_here':
        print("❌ Please set your ANTHROPIC_API_KEY in the .env file")
        return None
    
    client = anthropic.Anthropic(api_key=api_key)
    
    try:
        print("🤖 Sending to Claude for summarization...")
        
        full_prompt = f"{prompt}\n\n---\n\nChannel messages:\n\n{context}"
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": full_prompt
            }]
        )
        
        return response.content[0].text
        
    except Exception as e:
        print(f"❌ Error calling Claude API: {str(e)}")
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python summarize_channel.py <channel_name>")
        print("Example: python summarize_channel.py lab-notes-ben-goldhaber")
        return
    
    channel_name = sys.argv[1]
    
    # Find the most recent JSON file
    data_dir = "data"
    if not os.path.exists(data_dir):
        print("❌ No data directory found. Run collect_messages.py first.")
        return
        
    json_files = [f for f in os.listdir(data_dir) if f.startswith("messages_") and f.endswith(".json")]
    if not json_files:
        print("❌ No message files found in data directory")
        return
    
    latest_file = sorted(json_files)[-1]
    filepath = os.path.join(data_dir, latest_file)
    
    print(f"📂 Loading data from: {filepath}")
    
    # Load the JSON data
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Find the requested channel
    channels = data.get('channels', {})
    if channel_name not in channels:
        print(f"❌ Channel '{channel_name}' not found in data")
        print("Available channels:")
        for name in channels.keys():
            print(f"  - {name}")
        return
    
    channel_data = channels[channel_name]
    
    # Check if channel has messages
    if channel_data.get('error'):
        print(f"❌ Channel '{channel_name}' had an error: {channel_data['error']}")
        return
    
    message_count = channel_data.get('message_count', 0)
    reply_count = channel_data.get('thread_replies_count', 0)
    print(f"📊 Channel '{channel_name}': {message_count} messages + {reply_count} replies")
    
    # Load the prompt
    prompt = load_prompt()
    if not prompt:
        return
    
    # Prepare context
    print("📝 Preparing context...")
    context = prepare_channel_context(channel_data)
    
    # Summarize with Claude
    summary = summarize_channel_with_claude(prompt, context)
    
    if summary:
        print("\n" + "="*60)
        print(f"SUMMARY: #{channel_name}")
        print("="*60)
        print(summary)
        print("="*60)
    else:
        print("❌ Failed to generate summary")

if __name__ == "__main__":
    main()