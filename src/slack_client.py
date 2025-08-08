import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class TownCrierSlackClient:
    def __init__(self):
        load_dotenv()
        self.token = os.getenv('SLACK_BOT_TOKEN')
        
        if not self.token:
            raise ValueError("SLACK_BOT_TOKEN not found in environment variables")
        
        self.client = WebClient(token=self.token)
        print(f"Initialized Slack client with token: {self.token[:12]}...")
    
    def test_connection(self):
        try:
            time.sleep(30)  # Rate limiting before API call
            response = self.client.auth_test()
            print(f"✅ Connected to Slack successfully!")
            print(f"   Bot name: {response['user']}")
            print(f"   Team: {response['team']}")
            print(f"   User ID: {response['user_id']}")
            return response
        except SlackApiError as e:
            print(f"❌ Failed to connect to Slack: {e.response['error']}")
            raise
    
    def get_all_accessible_channels(self):
        try:
            # Get all public channels the bot has access to
            print("Getting all accessible public channels...")
            time.sleep(30)  # Rate limiting before API call
            response = self.client.conversations_list(
                types="public_channel",
                limit=200
            )
            
            all_channels = response['channels']
            print(f"Found {len(all_channels)} total public channels")
            
            # Filter for channels the bot is actually a member of
            accessible_channels = []
            for channel in all_channels:
                if channel.get('is_member', False):
                    accessible_channels.append(channel)
            
            print(f"Found {len(accessible_channels)} accessible channels:")
            for channel in accessible_channels:
                print(f"  - {channel['name']} (ID: {channel['id']})")
            
            return accessible_channels
            
        except SlackApiError as e:
            print(f"❌ Failed to get channels: {e.response['error']}")
            raise
    
    def get_lab_channels(self):
        """Backward compatibility - get lab-notes and surface-area channels only"""
        try:
            all_channels = self.get_all_accessible_channels()
            
            # Filter for lab-notes-* and surface-area-* channels
            lab_channels = []
            for channel in all_channels:
                name = channel['name']
                if name.startswith('lab-notes-') or name.startswith('surface-area-'):
                    lab_channels.append(channel)
            
            print(f"Filtered to {len(lab_channels)} lab/surface-area channels:")
            for channel in lab_channels:
                print(f"  - {channel['name']} (ID: {channel['id']})")
            
            return lab_channels
            
        except SlackApiError as e:
            print(f"❌ Failed to get lab channels: {e.response['error']}")
            raise
    
    def get_channel_history(self, channel_id, days=7):
        try:
            # Calculate timestamp for N days ago
            oldest_time = datetime.now() - timedelta(days=days)
            oldest_timestamp = oldest_time.timestamp()
            
            print(f"Fetching messages from last {days} days (since {oldest_time.strftime('%Y-%m-%d %H:%M:%S')})...")
            
            all_messages = []
            cursor = None
            page_count = 0
            
            while True:
                page_count += 1
                time.sleep(30)  # Rate limiting before API call
                
                # Build API call parameters
                # Note: Slack's conversations.history API now has a limit of 15 messages per request
                # (reduced from previous limit of 100). We use pagination to get all messages
                # within our 7-day window by making multiple requests with cursor.
                params = {
                    'channel': channel_id,
                    'limit': 15  # Current Slack API limit per request
                }
                
                if cursor:
                    params['cursor'] = cursor
                
                print(f"  Page {page_count}: requesting up to {params['limit']} messages...")
                
                # Retry logic for rate limits
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        response = self.client.conversations_history(**params)
                        break  # Success, exit retry loop
                    except SlackApiError as e:
                        if e.response['error'] == 'rate_limited':
                            retry_after = int(e.response.get('headers', {}).get('Retry-After', 120))
                            print(f"  Rate limited, retrying in {retry_after} seconds (attempt {retry + 1}/{max_retries})...")
                            time.sleep(retry_after)
                        else:
                            raise  # Re-raise non-rate-limit errors
                else:
                    # All retries exhausted
                    raise SlackApiError("Rate limit retries exhausted", response={'error': 'rate_limited'})
                
                page_messages = response['messages']
                
                # Filter messages to only include those within our 7-day window
                messages_in_window = []
                for msg in page_messages:
                    msg_timestamp = float(msg.get('ts', 0))
                    if msg_timestamp >= oldest_timestamp:
                        messages_in_window.append(msg)
                    else:
                        # We've reached messages older than our window, stop here
                        print(f"  Reached messages older than {days} days, stopping pagination")
                        all_messages.extend(messages_in_window)
                        print(f"Found {len(all_messages)} messages total in channel from last {days} days")
                        return all_messages
                
                all_messages.extend(messages_in_window)
                print(f"  Page {page_count}: got {len(messages_in_window)} messages in window (total: {len(all_messages)})")
                
                # Check if we have more pages
                if not response.get('has_more', False):
                    break
                    
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
            
            print(f"Found {len(all_messages)} messages total in channel from last {days} days")
            
            return all_messages
            
        except SlackApiError as e:
            print(f"❌ Failed to get channel history: {e.response['error']}")
            raise
    
    def get_thread_replies(self, channel_id, thread_ts):
        try:
            time.sleep(30)  # Rate limiting before API call
            response = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts
            )
            
            replies = response['messages']
            # First message is the original, rest are replies
            return replies[1:] if len(replies) > 1 else []
            
        except SlackApiError as e:
            print(f"❌ Failed to get thread replies: {e.response['error']}")
            return []
    
    def post_message(self, channel_id, text, max_retries=3):
        for attempt in range(max_retries):
            try:
                time.sleep(30)  # Rate limiting before API call
                response = self.client.chat_postMessage(
                    channel=channel_id,
                    text=text
                )
                print(f"✅ Message posted successfully!")
                return response
                
            except SlackApiError as e:
                error_code = e.response['error']
                print(f"❌ Failed to post message (attempt {attempt + 1}/{max_retries}): {error_code}")
                
                if error_code == 'rate_limited':
                    retry_after = int(e.response.get('headers', {}).get('Retry-After', 60))
                    print(f"   Rate limited, retrying in {retry_after} seconds...")
                    time.sleep(retry_after)
                elif attempt < max_retries - 1:  # Not the last attempt
                    print(f"   Retrying in 10 seconds...")
                    time.sleep(10)
                else:
                    print(f"   All {max_retries} attempts failed")
                    raise
    
    def post_reply(self, channel_id, thread_ts, text, max_retries=3):
        for attempt in range(max_retries):
            try:
                time.sleep(5)  # Reduced delay for replies
                response = self.client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=text
                )
                print(f"✅ Reply posted successfully!")
                return response
                
            except SlackApiError as e:
                error_code = e.response['error']
                print(f"❌ Failed to post reply (attempt {attempt + 1}/{max_retries}): {error_code}")
                
                if error_code == 'rate_limited':
                    retry_after = int(e.response.get('headers', {}).get('Retry-After', 60))
                    print(f"   Rate limited, retrying in {retry_after} seconds...")
                    time.sleep(retry_after)
                elif attempt < max_retries - 1:  # Not the last attempt
                    print(f"   Retrying in 10 seconds...")
                    time.sleep(10)
                else:
                    print(f"   All {max_retries} attempts failed")
                    raise
    
    def upload_file(self, channel_id, file_path, filename=None, initial_comment=None):
        try:
            time.sleep(30)  # Rate limiting before API call
            
            if filename is None:
                filename = os.path.basename(file_path)
            
            response = self.client.files_upload_v2(
                channel=channel_id,
                file=file_path,
                filename=filename,
                initial_comment=initial_comment
            )
            print(f"✅ File uploaded successfully!")
            return response
            
        except SlackApiError as e:
            print(f"❌ Failed to upload file: {e.response['error']}")
            raise
    
    def get_user_info(self, user_id):
        try:
            time.sleep(30)  # Rate limiting before API call
            response = self.client.users_info(user=user_id)
            user = response['user']
            return {
                'id': user_id,
                'name': user.get('name', 'Unknown'),
                'real_name': user.get('real_name', 'Unknown'),
                'display_name': user.get('profile', {}).get('display_name', ''),
            }
        except SlackApiError as e:
            print(f"⚠️ Failed to get user info for {user_id}: {e.response['error']}")
            return {
                'id': user_id,
                'name': 'Unknown',
                'real_name': 'Unknown',
                'display_name': '',
            }