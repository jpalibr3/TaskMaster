#!/usr/bin/env python3
"""
Simple test to debug Zapier MCP responses
"""

import os
import json
import requests

def test_simple_zapier_call():
    zapier_mcp_url = os.getenv("ZAPIER_MCP_SERVER_URL")
    zapier_mcp_api_key = os.getenv("ZAPIER_MCP_API_KEY")
    
    headers = {
        "Authorization": f"Bearer {zapier_mcp_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    # Try the simplest possible search
    simple_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "salesforce_find_record",
            "arguments": {
                "object": "Account",
                "searchField": "Name",
                "searchValue": "Zapier",
                "operator": "contains"
            }
        }
    }
    
    print("Testing simple Zapier MCP call...")
    try:
        response = requests.post(zapier_mcp_url, headers=headers, json=simple_payload, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Response length: {len(response.text)}")
        print("Response content:")
        print(response.text)
        
        if response.status_code == 200:
            # Parse SSE response
            events = []
            lines = response.text.strip().split('\n')
            current_event = {}
            
            for line in lines:
                line = line.strip()
                if line.startswith('event:'):
                    if current_event:
                        events.append(current_event)
                    current_event = {'type': line[6:].strip()}
                elif line.startswith('data:'):
                    data = line[5:].strip()
                    if data:
                        try:
                            current_event['data'] = json.loads(data)
                        except json.JSONDecodeError:
                            current_event['data'] = data
                elif line == '' and current_event:
                    events.append(current_event)
                    current_event = {}
            
            if current_event:
                events.append(current_event)
            
            print(f"\nParsed {len(events)} events:")
            for i, event in enumerate(events):
                print(f"Event {i+1}: {event.get('type', 'unknown')}")
                if event.get('data'):
                    data = event['data']
                    print(f"  Data type: {type(data)}")
                    if isinstance(data, dict):
                        print(f"  Keys: {list(data.keys())}")
                        if 'result' in data:
                            result = data['result']
                            print(f"  Result type: {type(result)}")
                            print(f"  Result preview: {str(result)[:500]}...")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_simple_zapier_call()