#!/usr/bin/env python3
"""
Generate comprehensive API documentation for all endpoints
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to Python path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

import logging
from glob import glob

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_routes_from_file(file_path):
    """Extract route definitions from a Python file"""
    routes = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Look for @router.get, @router.post, etc.
        import re
        
        # Pattern to match route decorators
        route_pattern = r'@router\.(get|post|put|delete|patch)\([\s\S]*?\)\s*(?:async\s+)?def\s+(\w+)'
        
        matches = re.finditer(route_pattern, content, re.MULTILINE)
        
        for match in matches:
            method = match.group(1).upper()
            function_name = match.group(2)
            
            # Extract the route path from the decorator
            decorator_content = match.group(0)
            path_match = re.search(r'@router\.\w+\(\s*["\']([^"\']+)["\']', decorator_content)
            
            if path_match:
                path = path_match.group(1)
                
                # Look for response_model or other metadata
                response_model = None
                if 'response_model=' in decorator_content:
                    response_match = re.search(r'response_model=(\w+)', decorator_content)
                    if response_match:
                        response_model = response_match.group(1)
                
                # Look for tags
                tags = []
                if 'tags=' in decorator_content:
                    tags_match = re.search(r'tags=\[(.*?)\]', decorator_content)
                    if tags_match:
                        tags_content = tags_match.group(1)
                        tags = [tag.strip().strip('"\'') for tag in tags_content.split(',')]
                
                routes.append({
                    'method': method,
                    'path': path,
                    'function': function_name,
                    'response_model': response_model,
                    'tags': tags,
                    'file': file_path
                })
    except Exception as e:
        logger.warning(f"Error reading {file_path}: {e}")
    
    return routes

def analyze_main_py():
    """Analyze main.py for router includes and prefixes"""
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract router includes
        import re
        include_pattern = r'app\.include_router\(([^,]+)(?:,\s*prefix=[\"\']([^\"\']*)[\"\']])?'
        
        includes = []
        matches = re.finditer(include_pattern, content)
        
        for match in matches:
            router_name = match.group(1).strip()
            prefix = match.group(2) if match.group(2) else ""
            includes.append({
                'router': router_name,
                'prefix': prefix
            })
        
        return includes
    except Exception as e:
        logger.error(f"Error analyzing main.py: {e}")
        return []

def main():
    """Generate comprehensive API documentation"""
    logger.info("🚀 GENERATING COMPREHENSIVE API DOCUMENTATION")
    logger.info("=" * 60)
    
    # Find all route files
    route_files = []
    for pattern in ['app/api/**/*.py', 'app/api/*.py']:
        route_files.extend(glob(pattern, recursive=True))
    
    # Remove __init__.py files
    route_files = [f for f in route_files if not f.endswith('__init__.py')]
    
    logger.info(f"📋 Found {len(route_files)} route files:")
    for file in route_files:
        logger.info(f"   - {file}")
    
    # Analyze main.py for router includes
    router_includes = analyze_main_py()
    
    logger.info(f"\n📋 Router includes from main.py:")
    for include in router_includes:
        logger.info(f"   - {include['router']} -> prefix: '{include['prefix']}'")
    
    # Extract all routes
    all_routes = []
    for file_path in route_files:
        routes = extract_routes_from_file(file_path)
        for route in routes:
            route['file_name'] = os.path.basename(file_path)
        all_routes.extend(routes)
    
    # Group routes by category/file
    routes_by_file = {}
    for route in all_routes:
        file_name = route['file_name']
        if file_name not in routes_by_file:
            routes_by_file[file_name] = []
        routes_by_file[file_name].append(route)
    
    # Generate documentation
    doc_content = generate_documentation(routes_by_file, router_includes)
    
    # Write to file
    with open('API_ENDPOINTS_DOCUMENTATION.md', 'w', encoding='utf-8') as f:
        f.write(doc_content)
    
    logger.info(f"\n✅ API documentation generated: API_ENDPOINTS_DOCUMENTATION.md")
    logger.info(f"📊 Total endpoints found: {len(all_routes)}")
    
    # Print summary to console
    print_summary(routes_by_file)

def determine_full_path(route_path, file_name, router_includes):
    """Determine the full API path based on router includes"""
    # Common prefix mappings based on main.py analysis
    prefix_mappings = {
        'cleaned_routes.py': '/api/v1',
        'cleaned_auth_routes.py': '/api/v1', 
        'settings_routes.py': '/api/v1',
        'engagement_routes.py': '/api/v1',
        'credit_routes.py': '/api/v1',
        'lists_routes.py': '/api/v1',
        'discovery_routes.py': '/api/v1',
        'campaigns_routes.py': '/api',
        'health.py': '/api',
        'brand_proposals_routes.py': '/api'
    }
    
    prefix = prefix_mappings.get(file_name, '/api')
    
    # Handle special cases
    if 'admin' in file_name.lower():
        prefix = '/api/admin'
    
    return f"{prefix}{route_path}"

def generate_documentation(routes_by_file, router_includes):
    """Generate comprehensive markdown documentation"""
    
    doc = """# Analytics Following Backend - Complete API Documentation

## Overview
Complete API endpoint documentation for the Analytics Following Backend system.

**Base URL**: `http://localhost:8000` (development) / `https://your-domain.com` (production)

## Authentication
Most endpoints require authentication via JWT token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

---

"""
    
    # Sort files for better organization
    sorted_files = sorted(routes_by_file.keys())
    
    for file_name in sorted_files:
        routes = routes_by_file[file_name]
        
        # Determine category name
        category = file_name.replace('.py', '').replace('_', ' ').title()
        if 'routes' in category:
            category = category.replace(' Routes', '')
        
        doc += f"\n## {category}\n"
        doc += f"*Source: {file_name}*\n\n"
        
        # Group routes by path for better organization
        routes_by_path = {}
        for route in routes:
            full_path = determine_full_path(route['path'], file_name, router_includes)
            if full_path not in routes_by_path:
                routes_by_path[full_path] = []
            routes_by_path[full_path].append(route)
        
        # Sort paths
        for path in sorted(routes_by_path.keys()):
            path_routes = routes_by_path[path]
            
            doc += f"\n### `{path}`\n\n"
            
            for route in path_routes:
                doc += f"**{route['method']}** `{path}`\n"
                doc += f"- Function: `{route['function']}`\n"
                
                if route['response_model']:
                    doc += f"- Response Model: `{route['response_model']}`\n"
                
                if route['tags']:
                    doc += f"- Tags: {', '.join(route['tags'])}\n"
                
                doc += "\n"
    
    doc += """
---

## Response Format

### Success Response
```json
{
  "status": "success",
  "data": { ... },
  "message": "Optional success message"
}
```

### Error Response
```json
{
  "detail": "Error message",
  "status_code": 400
}
```

## Common Status Codes
- `200` - OK
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

## Rate Limiting
- Maximum 500 requests per hour per user
- Maximum 5 concurrent requests

## Credits System
Many endpoints consume credits from the user's credit wallet. Credit costs are returned in response headers when applicable.

"""
    
    return doc

def print_summary(routes_by_file):
    """Print a summary of all endpoints to console"""
    print("\n" + "="*60)
    print("📋 COMPLETE API ENDPOINTS SUMMARY")
    print("="*60)
    
    total_endpoints = 0
    
    for file_name in sorted(routes_by_file.keys()):
        routes = routes_by_file[file_name]
        total_endpoints += len(routes)
        
        category = file_name.replace('.py', '').replace('_', ' ').title()
        print(f"\n📁 {category} ({len(routes)} endpoints)")
        
        # Group by method
        methods = {}
        for route in routes:
            full_path = determine_full_path(route['path'], file_name, [])
            method = route['method']
            if method not in methods:
                methods[method] = []
            methods[method].append(full_path)
        
        for method in sorted(methods.keys()):
            print(f"   {method}: {len(methods[method])} endpoints")
            for path in sorted(methods[method]):
                print(f"      {method} {path}")
    
    print(f"\n🎯 TOTAL: {total_endpoints} API endpoints")
    print("="*60)

if __name__ == "__main__":
    main()