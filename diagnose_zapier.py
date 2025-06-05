#!/usr/bin/env python3
"""
Comprehensive Zapier MCP diagnostic tool
"""

import os
import json
import requests
import time

def diagnose_zapier_mcp():
    """Run comprehensive diagnostics on Zapier MCP integration."""
    
    zapier_mcp_url = os.getenv("ZAPIER_MCP_SERVER_URL")
    zapier_mcp_api_key = os.getenv("ZAPIER_MCP_API_KEY")
    
    print("Zapier MCP Diagnostic Report")
    print("=" * 50)
    print(f"Server URL: {zapier_mcp_url}")
    print(f"API Key: {zapier_mcp_api_key[:15]}...{zapier_mcp_api_key[-10:]}")
    
    headers = {
        "Authorization": f"Bearer {zapier_mcp_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    # Test 1: Basic connectivity
    print("\n1. Testing basic connectivity...")
    try:
        basic_response = requests.get(zapier_mcp_url.replace('/mcp', ''), timeout=10)
        print(f"   Basic HTTP status: {basic_response.status_code}")
    except Exception as e:
        print(f"   Basic connectivity failed: {e}")
    
    # Test 2: Tools list (short timeout)
    print("\n2. Testing tools list...")
    tools_payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    
    try:
        start_time = time.time()
        response = requests.post(zapier_mcp_url, headers=headers, json=tools_payload, timeout=15)
        duration = time.time() - start_time
        
        print(f"   Status: {response.status_code}")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Response size: {len(response.text)} chars")
        
        if response.status_code == 200:
            # Quick parse to count tools
            if '"tools":[' in response.text:
                tools_section = response.text.split('"tools":[')[1].split(']')[0]
                tool_count = tools_section.count('"name":')
                print(f"   Tools found: {tool_count}")
                
                # Extract first few tool names
                import re
                tool_names = re.findall(r'"name":"([^"]+)"', tools_section)
                print(f"   Sample tools: {tool_names[:5]}")
        else:
            print(f"   Error response: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("   Request timed out (>15s)")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Simple search with minimal parameters
    print("\n3. Testing simple search...")
    simple_search = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "salesforce_find_record",
            "arguments": {
                "instructions": "Find any account"
            }
        }
    }
    
    try:
        start_time = time.time()
        response = requests.post(zapier_mcp_url, headers=headers, json=simple_search, timeout=20)
        duration = time.time() - start_time
        
        print(f"   Status: {response.status_code}")
        print(f"   Duration: {duration:.2f}s")
        
        if response.status_code == 200:
            # Check for common response patterns
            if "followUpQuestion" in response.text:
                print("   Response: Zapier asking for more details")
            elif "result" in response.text:
                print("   Response: Got result data")
            elif "error" in response.text:
                print("   Response: Error returned")
            else:
                print("   Response: Unknown format")
            
            print(f"   Sample response: {response.text[:300]}...")
        else:
            print(f"   Error: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("   Search request timed out (>20s)")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 4: Check Salesforce connection status
    print("\n4. Testing Salesforce connection...")
    salesforce_test = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "salesforce_api_request_beta",
            "arguments": {
                "instructions": "Test Salesforce connection"
            }
        }
    }
    
    try:
        start_time = time.time()
        response = requests.post(zapier_mcp_url, headers=headers, json=salesforce_test, timeout=15)
        duration = time.time() - start_time
        
        print(f"   Status: {response.status_code}")
        print(f"   Duration: {duration:.2f}s")
        
        if response.status_code == 200:
            if "unauthorized" in response.text.lower():
                print("   Issue: Salesforce authentication problem")
            elif "connected" in response.text.lower():
                print("   Status: Salesforce appears connected")
            elif "error" in response.text.lower():
                print("   Issue: Salesforce error detected")
            else:
                print("   Status: Connection test completed")
                
            print(f"   Sample response: {response.text[:300]}...")
        else:
            print(f"   Error: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("   Salesforce test timed out (>15s)")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 50)
    print("Diagnostic Summary:")
    print("- If tools list works but searches timeout: Salesforce connection issue")
    print("- If getting 'followUpQuestion' responses: Need more specific parameters")
    print("- If authentication errors: Check API key and permissions")
    print("- If all tests fail: Check Zapier MCP server URL and credentials")

if __name__ == "__main__":
    diagnose_zapier_mcp()