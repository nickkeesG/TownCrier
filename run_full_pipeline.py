#!/usr/bin/env python3

import json
import os
import random
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import anthropic
from src.slack_client import TownCrierSlackClient

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

def step1_collect_messages():
    """Step 1: Collect messages from Slack"""
    print("🔄 STEP 1: Collecting messages from Slack...")
    step_start = time.time()
    
    # Import and run the collection logic
    from collect_messages import collect_all_messages
    
    try:
        data = collect_all_messages()
        step_time = time.time() - step_start
        print(f"✅ Step 1 completed in {step_time/60:.1f} minutes")
        return True, step_time
    except Exception as e:
        print(f"❌ Step 1 failed: {str(e)}")
        return False, time.time() - step_start

def step2_generate_summaries():
    """Step 2: Generate summaries for all channels"""
    print("\n🔄 STEP 2: Generating summaries...")
    step_start = time.time()
    
    try:
        # Find the most recent JSON file
        data_dir = "data"
        json_files = [f for f in os.listdir(data_dir) if f.startswith("messages_") and f.endswith(".json")]
        if not json_files:
            print("❌ No message files found")
            return False, 0
        
        latest_file = sorted(json_files)[-1]
        filepath = os.path.join(data_dir, latest_file)
        
        # Load the JSON data
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Set up Claude client
        load_dotenv()
        api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not api_key or api_key == 'your_anthropic_api_key_here':
            print("❌ Please set your ANTHROPIC_API_KEY in the .env file")
            return False, 0
        
        anthropic_client = anthropic.Anthropic(api_key=api_key)
        
        # Load the prompt
        prompt = load_prompt()
        if not prompt:
            return False, 0
        
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
            print("❌ No accessible channels found with messages")
            return False, 0
        
        # Randomize the order
        random.shuffle(target_channels)
        print(f"📊 Found {len(target_channels)} channels to summarize")
        
        # Generate summaries for all channels
        all_summaries = []
        
        for i, channel_name in enumerate(target_channels, 1):
            print(f"🤖 [{i}/{len(target_channels)}] Summarizing #{channel_name}...")
            
            channel_data = channels[channel_name]
            context = prepare_channel_context(channel_data)
            summary = summarize_channel_with_claude(prompt, context, anthropic_client)
            
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
        
        # Create final output and save
        if all_summaries:
            final_output = "\n\n".join(all_summaries)
            
            # Save to file
            os.makedirs("summaries", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"summaries/summary_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(final_output)
            
            step_time = time.time() - step_start
            print(f"✅ Step 2 completed in {step_time/60:.1f} minutes - saved to {filename}")
            return True, step_time
        else:
            print("❌ No summaries were generated")
            return False, time.time() - step_start
            
    except Exception as e:
        print(f"❌ Step 2 failed: {str(e)}")
        return False, time.time() - step_start

def step3_post_to_slack():
    """Step 3: Post the summary to Slack"""
    print("\n🔄 STEP 3: Posting summary to Slack...")
    step_start = time.time()
    
    try:
        # Find the most recent summary file
        summaries_dir = "summaries"
        summary_files = [f for f in os.listdir(summaries_dir) if f.startswith("summary_") and f.endswith(".txt")]
        if not summary_files:
            print("❌ No summary files found")
            return False, 0
        
        latest_file = sorted(summary_files)[-1]
        filepath = os.path.join(summaries_dir, latest_file)
        
        # Load the summary content
        with open(filepath, 'r', encoding='utf-8') as f:
            summary_content = f.read()
        
        # Initialize Slack client
        client = TownCrierSlackClient()
        
        # Test connection
        client.test_connection()
        
        # Get all channels to find daily-overview
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
            return False, 0
        
        print(f"✅ Found #{target_channel['name']} (ID: {target_channel['id']})")
        
        # Post 7-day date range first
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        date_range = f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"
        print(f"📤 Posting date message to #{target_channel['name']}...")
        
        date_response = client.post_message(target_channel['id'], date_range)
        thread_ts = date_response.get('ts')
        print(f"✅ Date message posted successfully!")
        
        # Post the summary as a reply
        print(f"📤 Posting summary as reply...")
        summary_response = client.post_reply(target_channel['id'], thread_ts, summary_content)
        print(f"✅ Summary posted as reply successfully!")
        
        step_time = time.time() - step_start
        print(f"✅ Step 3 completed in {step_time/60:.1f} minutes")
        return True, step_time
        
    except Exception as e:
        print(f"❌ Step 3 failed: {str(e)}")
        return False, time.time() - step_start

def step4_post_to_external_endpoint():
    """Step 4: Post the most recent JSON to external endpoint"""
    print("\n🔄 STEP 4: Posting latest JSON to external endpoint...")
    step_start = time.time()
    
    try:
        # Import the post_latest_data functionality
        from post_latest_data import find_most_recent_json, post_json_to_slack
        
        # Get bearer token from environment variable
        bearer_token = os.getenv('BEARER_TOKEN')
        if not bearer_token:
            print("⚠️  BEARER_TOKEN not set - skipping external endpoint posting")
            print("   Set with: export BEARER_TOKEN='your_token_here'")
            return True, 0  # Don't fail the pipeline, just skip this step
        
        # Find and post the most recent JSON
        most_recent_file = find_most_recent_json()
        print(f"📤 Posting {most_recent_file.name} to external endpoint...")
        
        success = post_json_to_slack(most_recent_file, bearer_token)
        
        step_time = time.time() - step_start
        if success:
            print(f"✅ Step 4 completed in {step_time:.1f} seconds")
            return True, step_time
        else:
            print(f"❌ Step 4 failed in {step_time:.1f} seconds")
            return False, step_time
            
    except Exception as e:
        print(f"❌ Step 4 failed: {str(e)}")
        return False, time.time() - step_start

def main():
    print("=" * 80)
    print("🚀 TOWNCRIER FULL PIPELINE")
    print("=" * 80)
    
    total_start = time.time()
    
    # Step 1: Collect messages
    success1, time1 = step1_collect_messages()
    if not success1:
        print("\n❌ Pipeline failed at Step 1")
        return
    
    # Step 2: Generate summaries
    success2, time2 = step2_generate_summaries()
    if not success2:
        print("\n❌ Pipeline failed at Step 2")
        return
    
    # Step 3: Post to Slack
    success3, time3 = step3_post_to_slack()
    if not success3:
        print("\n❌ Pipeline failed at Step 3")
        return
    
    # Step 4: Post to external endpoint
    success4, time4 = step4_post_to_external_endpoint()
    if not success4:
        print("\n⚠️  Step 4 failed, but continuing...")
    
    # Final summary
    total_time = time.time() - total_start
    
    print("\n" + "=" * 80)
    print("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print(f"⏱️  Step 1 (Collection): {time1/60:.1f} minutes")
    print(f"⏱️  Step 2 (Summarization): {time2/60:.1f} minutes") 
    print(f"⏱️  Step 3 (Posting): {time3/60:.1f} minutes")
    print(f"⏱️  Step 4 (External): {time4:.1f} seconds")
    print(f"⏱️  Total Time: {total_time/60:.1f} minutes ({total_time/3600:.1f} hours)")
    print("=" * 80)

if __name__ == "__main__":
    main()