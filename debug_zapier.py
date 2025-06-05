#!/usr/bin/env python3
"""
Debug script to test Zapier MCP integration and see raw responses
"""

import os
import json
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_zapier_mcp():
    """Debug the Zapier MCP integration to see what's happening."""
    
    zapier_mcp_url = os.getenv("ZAPIER_MCP_SERVER_URL")
    zapier_mcp_api_key = os.getenv("ZAPIER_MCP_API_KEY")
    
    headers = {
        "Authorization": f"Bearer {zapier_mcp_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    # Test the exact query that's working but showing "Unknown"
    test_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "salesforce_find_record",
            "arguments": {
                "instructions": "Find Salesforce Account records where the Account Name contains 'Zapier', expecting multiple results"
            }
        }
    }
    
    print("Testing Zapier MCP with optimized query...")
    try:
        response = requests.post(zapier_mcp_url, headers=headers, json=test_payload, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Raw response length: {len(response.text)}")
        print("\n" + "="*80)
        print("RAW RESPONSE:")
        print("="*80)
        print(response.text)
        print("="*80)
        
        # Parse the response
        if response.status_code == 200:
            events = parse_sse_response(response.text)
            print(f"\nParsed {len(events)} events:")
            
            for i, event in enumerate(events):
                print(f"\nEvent {i+1}:")
                print(f"  Type: {event.get('type', 'unknown')}")
                if event.get('data'):
                    data = event['data']
                    print(f"  Data type: {type(data)}")
                    if isinstance(data, dict):
                        print(f"  Data keys: {list(data.keys())}")
                        
                        # Look for the actual Salesforce data
                        if 'result' in data:
                            result = data['result']
                            print(f"  Result type: {type(result)}")
                            print(f"  Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                            
                            if isinstance(result, dict) and 'content' in result:
                                content = result['content']
                                print(f"  Content type: {type(content)}")
                                if isinstance(content, list) and len(content) > 0:
                                    first_content = content[0]
                                    print(f"  First content type: {type(first_content)}")
                                    if isinstance(first_content, dict) and 'text' in first_content:
                                        text_content = first_content['text']
                                        print(f"  Text content preview: {text_content[:500]}...")
                                        
                                        # Try to parse as JSON
                                        try:
                                            parsed_json = json.loads(text_content)
                                            print(f"  Parsed JSON type: {type(parsed_json)}")
                                            print(f"  Parsed JSON keys: {list(parsed_json.keys()) if isinstance(parsed_json, dict) else 'Not a dict'}")
                                            
                                            # Print the actual structure
                                            print(f"\n  ACTUAL SALESFORCE DATA STRUCTURE:")
                                            print(json.dumps(parsed_json, indent=2)[:1000] + "..." if len(str(parsed_json)) > 1000 else json.dumps(parsed_json, indent=2))
                                            
                                        except json.JSONDecodeError as e:
                                            print(f"  JSON parsing failed: {e}")
                                            print(f"  Raw text: {text_content}")
        
    except Exception as e:
        print(f"Error: {e}")

def parse_sse_response(response_text):
    """Parse Server-Sent Events response."""
    events = []
    lines = response_text.strip().split('\n')
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
    
    return events

if __name__ == "__main__":
    debug_zapier_mcp()