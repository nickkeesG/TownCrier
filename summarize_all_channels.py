#!/usr/bin/env python3

import json
import os
import random
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

def summarize_channel_with_claude(prompt, context, client):
    """Send the prompt and context to Claude for summarization"""
    try:
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
    
    # Set up Claude client
    load_dotenv()
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key or api_key == 'your_anthropic_api_key_here':
        print("❌ Please set your ANTHROPIC_API_KEY in the .env file")
        return
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Load the prompt
    prompt = load_prompt()
    if not prompt:
        return
    
    # Find all lab-notes and surface-area channels
    channels = data.get('channels', {})
    target_channels = []
    
    for channel_name in channels.keys():
        if channel_name.startswith('lab-notes-') or channel_name.startswith('surface-area-'):
            channel_data = channels[channel_name]
            # Skip channels with errors or no messages
            if not channel_data.get('error') and channel_data.get('message_count', 0) > 0:
                target_channels.append(channel_name)
    
    if not target_channels:
        print("❌ No accessible lab-notes or surface-area channels found with messages")
        return
    
    # Randomize the order of channels
    random.shuffle(target_channels)
    
    print(f"📊 Found {len(target_channels)} channels to summarize:")
    for channel_name in target_channels:
        channel_data = channels[channel_name]
        message_count = channel_data.get('message_count', 0)
        reply_count = channel_data.get('thread_replies_count', 0)
        print(f"  - #{channel_name}: {message_count} messages + {reply_count} replies")
    
    # Generate summaries for all channels
    all_summaries = []
    
    for i, channel_name in enumerate(target_channels, 1):
        print(f"\n🤖 [{i}/{len(target_channels)}] Summarizing #{channel_name}...")
        
        channel_data = channels[channel_name]
        context = prepare_channel_context(channel_data)
        summary = summarize_channel_with_claude(prompt, context, client)
        
        if summary:
            # Clean up unnecessary newlines in the summary
            cleaned_summary = "\n".join(line for line in summary.split('\n') if line.strip())
            
            # Format channel name as clickable link
            channel_id = channel_data.get('id')
            channel_link = f"<#{channel_id}|{channel_name}>" if channel_id else f"#{channel_name}"
            
            # Format the summary with channel header
            channel_summary = f"{channel_link}\n{cleaned_summary}"
            all_summaries.append(channel_summary)
            print(f"✅ Summary complete for #{channel_name}")
        else:
            print(f"❌ Failed to summarize #{channel_name}")
    
    # Create final output
    if all_summaries:
        final_output = "\n\n".join(all_summaries)
        
        # Print to terminal
        print("\n" + "="*80)
        print(final_output)
        print("="*80)
        
        # Save to file
        os.makedirs("summaries", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"summaries/summary_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(final_output)
        
        print(f"\n💾 Summary saved to: {filename}")
        print(f"✅ Summarized {len(all_summaries)} channels successfully.")
    else:
        print("❌ No summaries were generated")

if __name__ == "__main__":
    main()