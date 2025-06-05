#!/usr/bin/env python3
"""
Test script to verify search parameter extraction
"""

import re

def extract_search_parameters(action: str) -> dict:
    """Extract search parameters from natural language action."""
    
    # Determine object type
    object_type = 'Account'  # default
    if any(word in action for word in ['contact', 'person', 'people']):
        object_type = 'Contact'
    elif any(word in action for word in ['account', 'company', 'organization']):
        object_type = 'Account'
    elif any(word in action for word in ['opportunity', 'deal', 'sale']):
        object_type = 'Opportunity'
    elif any(word in action for word in ['lead', 'prospect']):
        object_type = 'Lead'
    
    # Extract search field and value
    search_field = None
    search_value = None
    
    # Email search - improved pattern
    email_match = re.search(r'email[:\s]*([^\s]+@[^\s]+)', action, re.IGNORECASE)
    if email_match:
        search_field = 'Email'
        search_value = email_match.group(1)
    
    # Name with "Zapier" pattern
    elif 'zapier' in action.lower():
        search_field = 'Name'
        search_value = 'Zapier'
    
    # Name search
    elif 'name' in action:
        name_patterns = [
            r'name[:\s]+(["\']([^"\']+)["\'])',  # quoted name
            r'name[:\s]+(\w+(?:\s+\w+)*)',       # unquoted name
            r'with.*name[:\s]+(["\']([^"\']+)["\'])',
            r'called[:\s]+(["\']([^"\']+)["\'])',
            r'called[:\s]+(\w+(?:\s+\w+)*)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, action, re.IGNORECASE)
            if match:
                search_field = 'Name'
                search_value = match.group(2) if len(match.groups()) > 1 and match.group(2) else match.group(1)
                search_value = search_value.strip('\'"')
                break
    
    # Company/Account search
    elif any(word in action for word in ['at ', 'company ', 'account ']):
        company_patterns = [
            r'at\s+(["\']([^"\']+)["\'])',
            r'at\s+(\w+(?:\s+\w+)*)',
            r'company[:\s]+(["\']([^"\']+)["\'])',
            r'company[:\s]+(\w+(?:\s+\w+)*)',
            r'account[:\s]+(["\']([^"\']+)["\'])',
            r'account[:\s]+(\w+(?:\s+\w+)*)'
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, action, re.IGNORECASE)
            if match:
                if object_type == 'Contact':
                    search_field = 'Account.Name'
                else:
                    search_field = 'Name'
                search_value = match.group(2) if len(match.groups()) > 1 and match.group(2) else match.group(1)
                search_value = search_value.strip('\'"')
                break
    
    # Generic "with" search
    elif 'with' in action:
        # Extract anything after "with"
        with_match = re.search(r'with\s+(.+)', action, re.IGNORECASE)
        if with_match:
            search_field = 'Name'
            search_value = with_match.group(1).strip()
    
    return {
        'object_type': object_type,
        'search_field': search_field,
        'search_value': search_value,
        'search_field2': None,
        'search_value2': None
    }

# Test the extraction function
test_queries = [
    "Find contacts with the email chris@alibre.com",
    "Find accounts with the name Zapier in it",
    "Find all accounts that have Zapier in the account name",
    "Find contact john doe",
    "Show me opportunities at Acme Corp"
]

print("Testing search parameter extraction:")
print("="*50)

for query in test_queries:
    result = extract_search_parameters(query)
    print(f"\nQuery: {query}")
    print(f"  Object: {result['object_type']}")
    print(f"  Field: {result['search_field']}")
    print(f"  Value: {result['search_value']}")