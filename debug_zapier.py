#!/usr/bin/env python3
"""
Debug script to test Zapier MCP integration and see raw responses
"""

import os
import json
import requests
from datetime import datetime

def debug_zapier_mcp():
    """Debug the Zapier MCP integration to see what's happening."""
    
    # Get credentials
    zapier_mcp_url = os.getenv("ZAPIER_MCP_SERVER_URL")
    zapier_mcp_api_key = os.getenv("ZAPIER_MCP_API_KEY")
    
    if not zapier_mcp_url or not zapier_mcp_api_key:
        print("❌ Missing Zapier MCP credentials")
        return
    
    print(f"🔍 Testing Zapier MCP at: {zapier_mcp_url}")
    print(f"🔑 Using API key: {zapier_mcp_api_key[:10]}...{zapier_mcp_api_key[-10:]}")
    print("="*60)
    
    headers = {
        "Authorization": f"Bearer {zapier_mcp_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    # Test 1: List available tools
    print("\n1. Testing tools/list...")
    tools_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
    }
    
    try:
        response = requests.post(zapier_mcp_url, headers=headers, json=tools_payload, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Raw Response: {response.text[:1000]}...")
        
        if response.status_code == 200:
            events = parse_sse_response(response.text)
            print(f"Parsed {len(events)} events")
            
            for i, event in enumerate(events):
                print(f"Event {i+1}: {event.get('type', 'unknown')}")
                if event.get('data'):
                    data = event['data']
                    if isinstance(data, dict) and 'result' in data and 'tools' in data['result']:
                        tools = data['result']['tools']
                        print(f"Found {len(tools)} tools:")
                        for tool in tools[:10]:  # Show first 10
                            print(f"  - {tool.get('name', 'unnamed')}")
                        if len(tools) > 10:
                            print(f"  ... and {len(tools) - 10} more")
    
    except Exception as e:
        print(f"❌ Tools list error: {e}")
        return
    
    # Test 2: Try a simple search command
    print("\n2. Testing a simple search command...")
    
    search_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "salesforce_find_record",
            "arguments": {
                "instructions": "Find all accounts in Salesforce"
            }
        }
    }
    
    try:
        response = requests.post(zapier_mcp_url, headers=headers, json=search_payload, timeout=60)
        print(f"Status: {response.status_code}")
        print(f"Raw Response: {response.text[:2000]}...")
        
        if response.status_code == 200:
            events = parse_sse_response(response.text)
            print(f"Parsed {len(events)} events")
            
            for i, event in enumerate(events):
                print(f"Event {i+1}: {event.get('type', 'unknown')}")
                if event.get('data'):
                    data = event['data']
                    print(f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
                    if isinstance(data, dict) and 'result' in data:
                        result = data['result']
                        print(f"Result type: {type(result)}")
                        print(f"Result: {str(result)[:500]}...")
    
    except Exception as e:
        print(f"❌ Search command error: {e}")
    
    # Test 3: Try different tools
    print("\n3. Testing different search tools...")
    
    test_tools = [
        "salesforce_find_record_by_query",
        "salesforce_find_record_s",
        "salesforce_api_request_beta"
    ]
    
    for tool_name in test_tools:
        print(f"\nTesting {tool_name}...")
        
        test_payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": {
                    "instructions": "List all accounts"
                }
            }
        }
        
        try:
            response = requests.post(zapier_mcp_url, headers=headers, json=test_payload, timeout=30)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                events = parse_sse_response(response.text)
                for event in events:
                    if event.get('data') and isinstance(event['data'], dict):
                        if 'result' in event['data']:
                            result = event['data']['result']
                            print(f"  Result preview: {str(result)[:200]}...")
                            break
            else:
                print(f"  Error: {response.text[:200]}...")
        except Exception as e:
            print(f"  Error: {e}")

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