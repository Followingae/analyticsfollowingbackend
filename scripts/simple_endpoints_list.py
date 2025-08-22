#!/usr/bin/env python3
"""
Simple list of all API endpoints
"""

import re
from glob import glob
import os

def extract_routes_from_file(file_path):
    """Extract route definitions from a Python file"""
    routes = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match route decorators
        route_pattern = r'@router\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']'
        
        matches = re.finditer(route_pattern, content, re.MULTILINE)
        
        for match in matches:
            method = match.group(1).upper()
            path = match.group(2)
            
            routes.append({
                'method': method,
                'path': path,
                'file': os.path.basename(file_path)
            })
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return routes

def determine_prefix(file_name):
    """Determine API prefix based on file name"""
    prefixes = {
        'cleaned_routes.py': '/api/v1',
        'cleaned_auth_routes.py': '/api/v1', 
        'settings_routes.py': '/api/v1',
        'engagement_routes.py': '/api/v1',
        'credit_routes.py': '/api/v1',
        'lists_routes.py': '/api/v1',
        'discovery_routes.py': '/api/v1',
        'campaigns_routes.py': '/api',
        'health.py': '/api',
        'brand_proposals_routes.py': '/api',
        'enhanced_instagram_routes.py': '/api/v1',
        'legacy_credit_routes.py': '/api/v1'
    }
    
    if 'admin' in file_name:
        return '/api/admin'
    
    return prefixes.get(file_name, '/api')

def main():
    print("ANALYTICS FOLLOWING BACKEND - ALL API ENDPOINTS")
    print("=" * 60)
    
    # Find all route files
    route_files = []
    for pattern in ['app/api/**/*.py', 'app/api/*.py']:
        route_files.extend(glob(pattern, recursive=True))
    
    # Remove duplicates and __init__.py files
    route_files = list(set([f for f in route_files if not f.endswith('__init__.py')]))
    
    all_routes = []
    
    # Extract routes from each file
    for file_path in route_files:
        routes = extract_routes_from_file(file_path)
        for route in routes:
            prefix = determine_prefix(route['file'])
            full_path = f"{prefix}{route['path']}"
            all_routes.append({
                'method': route['method'],
                'path': full_path,
                'file': route['file'],
                'category': route['file'].replace('.py', '').replace('_routes', '').title()
            })
    
    # Sort routes by path
    all_routes.sort(key=lambda x: x['path'])
    
    # Group by category
    categories = {}
    for route in all_routes:
        category = route['category']
        if category not in categories:
            categories[category] = []
        categories[category].append(route)
    
    # Print organized output
    total_endpoints = 0
    
    print("\nBY CATEGORY:")
    print("-" * 40)
    
    for category in sorted(categories.keys()):
        routes = categories[category]
        total_endpoints += len(routes)
        
        print(f"\n{category.upper()} ({len(routes)} endpoints)")
        
        # Group by method
        methods = {}
        for route in routes:
            method = route['method']
            if method not in methods:
                methods[method] = []
            methods[method].append(route['path'])
        
        for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
            if method in methods:
                print(f"  {method}:")
                for path in sorted(methods[method]):
                    print(f"    {path}")
    
    print(f"\nTOTAL ENDPOINTS: {total_endpoints}")
    
    # Print all endpoints in simple list format
    print("\n" + "=" * 60)
    print("COMPLETE ENDPOINT LIST (for frontend team):")
    print("=" * 60)
    
    current_prefix = ""
    for route in all_routes:
        # Group by prefix for readability
        prefix = route['path'].split('/')[1:3]  # Get first two parts
        prefix_str = '/' + '/'.join(prefix)
        
        if prefix_str != current_prefix:
            current_prefix = prefix_str
            print(f"\n## {prefix_str.upper()} ENDPOINTS:")
        
        print(f"{route['method']:<6} {route['path']}")
    
    print(f"\nTOTAL: {total_endpoints} API endpoints available")

if __name__ == "__main__":
    main()