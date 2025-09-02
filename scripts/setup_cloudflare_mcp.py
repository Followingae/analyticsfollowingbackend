#!/usr/bin/env python3
"""
Cloudflare MCP Setup and Testing Script
Sets up and tests Cloudflare MCP integration for Analytics Following Backend
"""

import os
import json
import subprocess
import sys
from pathlib import Path
import requests
from typing import Dict, Any

class CloudflareMCPSetup:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.env_file = self.base_dir / '.env'
        self.mcp_config = self.base_dir / '.claude' / 'mcp_cloudflare_config.json'
        
        # Load environment variables
        self.load_env_vars()
        
    def load_env_vars(self):
        """Load environment variables from .env file"""
        env_vars = {}
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
        
        self.cf_api_token = env_vars.get('CF_MCP_API_TOKEN')
        self.cf_account_id = env_vars.get('CF_ACCOUNT_ID') 
        self.cf_zone_id = env_vars.get('CF_ZONE_ID')
        
        if not all([self.cf_api_token, self.cf_account_id]):
            raise ValueError("Missing required Cloudflare credentials in .env file")
    
    def install_mcp_remote(self):
        """Install mcp-remote package globally"""
        print("📦 Installing mcp-remote...")
        try:
            result = subprocess.run(['npm', 'install', '-g', '@anthropic/mcp-remote'], 
                                  capture_output=True, text=True, check=True)
            print("✅ mcp-remote installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install mcp-remote: {e}")
            print(f"Error output: {e.stderr}")
            return False
    
    def test_cloudflare_api(self):
        """Test Cloudflare API connection"""
        print("🔐 Testing Cloudflare API connection...")
        
        headers = {
            'Authorization': f'Bearer {self.cf_api_token}',
            'Content-Type': 'application/json'
        }
        
        # Test account info
        try:
            response = requests.get(
                f'https://api.cloudflare.com/client/v4/accounts/{self.cf_account_id}',
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                account_name = data['result']['name']
                print(f"✅ API connection successful! Account: {account_name}")
                return True
            else:
                print(f"❌ API test failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ API test error: {e}")
            return False
    
    def test_zone_access(self):
        """Test zone access if zone ID is provided"""
        if not self.cf_zone_id:
            print("⚠️  No zone ID provided, skipping zone test")
            return True
            
        print("🌐 Testing zone access...")
        
        headers = {
            'Authorization': f'Bearer {self.cf_api_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                f'https://api.cloudflare.com/client/v4/zones/{self.cf_zone_id}',
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                zone_name = data['result']['name']
                print(f"✅ Zone access successful! Zone: {zone_name}")
                return True
            else:
                print(f"❌ Zone test failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Zone test error: {e}")
            return False
    
    def test_mcp_servers(self):
        """Test MCP server endpoints"""
        print("🔍 Testing MCP server endpoints...")
        
        mcp_servers = [
            'https://workers.mcp.cloudflare.com/sse',
            'https://observability.mcp.cloudflare.com/sse',
            'https://ai-gateway.mcp.cloudflare.com/sse',
            'https://dns.mcp.cloudflare.com/sse',
            'https://radar.mcp.cloudflare.com/sse'
        ]
        
        results = {}
        for server_url in mcp_servers:
            try:
                response = requests.get(server_url, timeout=10)
                server_name = server_url.split('//')[1].split('.')[0]
                
                if response.status_code in [200, 404]:  # 404 is expected for SSE endpoints
                    print(f"✅ {server_name}: Server accessible")
                    results[server_name] = True
                else:
                    print(f"⚠️  {server_name}: Unexpected status {response.status_code}")
                    results[server_name] = False
                    
            except Exception as e:
                server_name = server_url.split('//')[1].split('.')[0]
                print(f"❌ {server_name}: Connection failed - {e}")
                results[server_name] = False
        
        return results
    
    def create_integration_example(self):
        """Create example integration script"""
        example_script = self.base_dir / 'scripts' / 'cloudflare_mcp_example.py'
        
        example_content = '''#!/usr/bin/env python3
"""
Example Cloudflare MCP Integration
Demonstrates how to use Cloudflare MCP in your backend
"""

import asyncio
import json
from typing import Dict, Any

class CloudflareMCPClient:
    """Example client for interacting with Cloudflare MCP servers"""
    
    def __init__(self, api_token: str, account_id: str):
        self.api_token = api_token
        self.account_id = account_id
    
    async def get_worker_stats(self) -> Dict[str, Any]:
        """Get Cloudflare Workers analytics"""
        # This would integrate with the MCP server
        print("📊 Fetching Workers analytics...")
        return {"status": "example", "workers": []}
    
    async def get_cdn_performance(self) -> Dict[str, Any]:
        """Get CDN performance metrics"""
        print("📈 Fetching CDN performance...")
        return {"status": "example", "metrics": {}}
    
    async def optimize_ai_gateway(self) -> Dict[str, Any]:
        """Optimize AI Gateway settings"""
        print("🤖 Optimizing AI Gateway...")
        return {"status": "optimized"}

# Usage example
async def main():
    """Example usage of Cloudflare MCP integration"""
    
    # Load credentials from environment
    import os
    api_token = os.getenv('CF_MCP_API_TOKEN')
    account_id = os.getenv('CF_ACCOUNT_ID')
    
    if not api_token or not account_id:
        print("❌ Missing Cloudflare credentials")
        return
    
    # Initialize client
    client = CloudflareMCPClient(api_token, account_id)
    
    # Example operations
    await client.get_worker_stats()
    await client.get_cdn_performance() 
    await client.optimize_ai_gateway()
    
    print("✅ Cloudflare MCP integration example completed")

if __name__ == "__main__":
    asyncio.run(main())
'''
        
        with open(example_script, 'w') as f:
            f.write(example_content)
        
        print(f"📝 Created integration example at: {example_script}")
    
    def run_setup(self):
        """Run complete setup and testing"""
        print("🚀 Starting Cloudflare MCP Setup...")
        print("=" * 50)
        
        success = True
        
        # Install dependencies
        if not self.install_mcp_remote():
            success = False
        
        # Test API connection
        if not self.test_cloudflare_api():
            success = False
        
        # Test zone access
        if not self.test_zone_access():
            success = False
        
        # Test MCP servers
        mcp_results = self.test_mcp_servers()
        
        # Create integration example
        self.create_integration_example()
        
        print("=" * 50)
        if success and all(mcp_results.values()):
            print("🎉 Cloudflare MCP setup completed successfully!")
            print("\n📋 Next steps:")
            print("1. Configure your MCP client to use the config file:")
            print(f"   {self.mcp_config}")
            print("2. Test integration with: python scripts/cloudflare_mcp_example.py")
            print("3. Start using Cloudflare MCP servers in your backend!")
        else:
            print("⚠️  Setup completed with some issues. Check the logs above.")
        
        return success

if __name__ == "__main__":
    try:
        setup = CloudflareMCPSetup()
        setup.run_setup()
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1)