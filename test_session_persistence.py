#!/usr/bin/env python3
"""
Test script to verify session persistence in Cagent API.
Tests that sessions continue running even when the client disconnects.
"""

import requests
import json
import time
import sys
from datetime import datetime

# API Configuration
API_URL = "https://cagent-api-950783879036.us-central1.run.app"
EMAIL = "eladrave@gmail.com"
PASSWORD = "password123"
AGENT_FILE = "Elad Team of agents.yaml"  # The file is already in user's private folder
TEST_PROMPT = """Look up Jolene Amit on linkedin. Find her email. If needed, search the web.
Then, email her an introduction email from me to introduce myself to her"""

class CagentAPITester:
    def __init__(self):
        self.session = requests.Session()
        self.jwt_token = None
        self.session_id = None
        
    def login(self):
        """Login and get JWT token"""
        print(f"[{datetime.now().isoformat()}] Logging in as {EMAIL}...")
        response = self.session.post(
            f"{API_URL}/api/auth/login",
            json={"email": EMAIL, "password": PASSWORD}
        )
        
        if response.status_code != 200:
            print(f"Login failed: {response.status_code} - {response.text}")
            return False
            
        data = response.json()
        self.jwt_token = data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.jwt_token}"})
        print(f"[{datetime.now().isoformat()}] Login successful!")
        return True
        
    def create_session(self):
        """Create a new chat session"""
        print(f"[{datetime.now().isoformat()}] Creating new session...")
        response = self.session.post(
            f"{API_URL}/api/sessions",
            json={
                "maxIterations": 50,
                "toolsApproved": True,
                "workingDir": "/work"
            }
        )
        
        if response.status_code != 200:
            print(f"Failed to create session: {response.status_code} - {response.text}")
            return False
            
        data = response.json()
        self.session_id = data.get("id")
        print(f"[{datetime.now().isoformat()}] Created session: {self.session_id}")
        return True
        
    def send_message(self, disconnect_after=5):
        """Send message to agent and disconnect after specified seconds"""
        print(f"[{datetime.now().isoformat()}] Sending message to agent...")
        
        # Prepare the message
        messages = [
            {
                "role": "user",
                "content": TEST_PROMPT
            }
        ]
        
        # Start streaming the response
        url = f"{API_URL}/api/sessions/{self.session_id}/agent/{AGENT_FILE}"
        
        # Use stream=True for SSE
        response = self.session.post(
            url,
            json=messages,
            stream=True,
            headers={
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {self.jwt_token}"
            }
        )
        
        if response.status_code != 200:
            print(f"Failed to send message: {response.status_code}")
            return False
            
        print(f"[{datetime.now().isoformat()}] Streaming started, will disconnect in {disconnect_after} seconds...")
        
        # Read stream for a few seconds then disconnect
        start_time = time.time()
        event_count = 0
        
        try:
            for line in response.iter_lines():
                if time.time() - start_time > disconnect_after:
                    print(f"[{datetime.now().isoformat()}] Disconnecting after {disconnect_after} seconds (received {event_count} events)...")
                    response.close()  # Simulate closing browser tab
                    break
                    
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        event_count += 1
                        data = line[6:]  # Remove 'data: ' prefix
                        try:
                            event = json.loads(data)
                            event_type = event.get('type', 'unknown')
                            print(f"[{datetime.now().isoformat()}] Event #{event_count}: {event_type}")
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Stream error (expected): {e}")
            
        return True
        
    def check_session_status(self, wait_time=60, check_interval=5):
        """Check if session continues processing after disconnect"""
        print(f"[{datetime.now().isoformat()}] Waiting {wait_time} seconds before checking session status...")
        time.sleep(wait_time)
        
        print(f"[{datetime.now().isoformat()}] Checking session status...")
        response = self.session.get(
            f"{API_URL}/api/sessions/{self.session_id}",
            headers={"Authorization": f"Bearer {self.jwt_token}"}
        )
        
        if response.status_code != 200:
            print(f"Failed to get session: {response.status_code}")
            return False
            
        data = response.json()
        messages = data.get("messages", [])
        
        print(f"[{datetime.now().isoformat()}] Session has {len(messages)} messages")
        
        # Check for assistant messages (indicating processing happened)
        assistant_messages = [m for m in messages if m.get("message", {}).get("role") == "assistant"]
        tool_messages = [m for m in messages if m.get("message", {}).get("role") == "tool"]
        
        print(f"[{datetime.now().isoformat()}] Found {len(assistant_messages)} assistant messages")
        print(f"[{datetime.now().isoformat()}] Found {len(tool_messages)} tool response messages")
        
        # Show message roles to debug
        roles = [m.get("message", {}).get("role", "unknown") for m in messages]
        print(f"[{datetime.now().isoformat()}] Message roles: {roles}")
        
        # Print last few messages to see activity
        if messages:
            print(f"\n[{datetime.now().isoformat()}] Last 3 messages:")
            for msg in messages[-3:]:
                role = msg.get("message", {}).get("role", "unknown")
                content = msg.get("message", {}).get("content", "")[:100]
                created = msg.get("createdAt", "unknown")
                print(f"  - [{created}] {role}: {content}...")
                
        return len(assistant_messages) > 0 or len(tool_messages) > 0
        
    def reconnect_and_stream(self):
        """Reconnect to the session and stream remaining events"""
        print(f"\n[{datetime.now().isoformat()}] Reconnecting to session {self.session_id}...")
        
        # Send empty message to reconnect to stream
        messages = []
        url = f"{API_URL}/api/sessions/{self.session_id}/agent/{AGENT_FILE}"
        
        response = self.session.post(
            url,
            json=messages,
            stream=True,
            headers={
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {self.jwt_token}"
            }
        )
        
        if response.status_code != 200:
            print(f"Failed to reconnect: {response.status_code}")
            return False
            
        print(f"[{datetime.now().isoformat()}] Reconnected! Streaming events for 10 seconds...")
        
        start_time = time.time()
        event_count = 0
        
        try:
            for line in response.iter_lines():
                if time.time() - start_time > 10:
                    print(f"[{datetime.now().isoformat()}] Stopping stream after 10 seconds...")
                    break
                    
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        event_count += 1
                        data = line[6:]
                        try:
                            event = json.loads(data)
                            event_type = event.get('type', 'unknown')
                            print(f"[{datetime.now().isoformat()}] Event: {event_type}")
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Stream ended: {e}")
            
        print(f"[{datetime.now().isoformat()}] Received {event_count} events after reconnection")
        return event_count > 0
        
    def run_test(self):
        """Run the full test sequence"""
        print("=" * 80)
        print("CAGENT SESSION PERSISTENCE TEST")
        print("=" * 80)
        
        # Step 1: Login
        if not self.login():
            print("❌ Login failed")
            return False
            
        # Step 2: Create session
        if not self.create_session():
            print("❌ Session creation failed")
            return False
            
        # Step 3: Send message and disconnect quickly
        if not self.send_message(disconnect_after=3):
            print("❌ Failed to send message")
            return False
            
        # Step 4: Check if session continues processing
        if not self.check_session_status(wait_time=60):
            print("❌ Session did not continue processing after disconnect")
            print("\n⚠️  ISSUE: Session appears to have stopped when client disconnected")
            print("This indicates the session persistence fix is not working properly.")
            return False
            
        # Step 5: Try to reconnect
        if self.reconnect_and_stream():
            print("✅ Successfully reconnected to ongoing session")
        
        print("\n" + "=" * 80)
        print("✅ TEST PASSED: Session continued processing after disconnect!")
        print(f"Session ID: {self.session_id}")
        print("=" * 80)
        return True

if __name__ == "__main__":
    tester = CagentAPITester()
    success = tester.run_test()
    sys.exit(0 if success else 1)