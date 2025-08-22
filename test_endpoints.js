const https = require('http');

async function testEndpoint(url, description) {
  return new Promise((resolve) => {
    const req = https.get(url, (res) => {
      console.log(`${description}: ${res.statusCode}`);
      resolve(res.statusCode);
    });
    
    req.on('error', (error) => {
      console.log(`${description}: ERROR - ${error.message}`);
      resolve(null);
    });
    
    req.setTimeout(5000, () => {
      req.destroy();
      console.log(`${description}: TIMEOUT`);
      resolve(null);
    });
  });
}

async function runTests() {
  console.log('🔍 Running Comprehensive Endpoint Tests...\n');
  
  const baseURL = 'http://localhost:8000';
  
  // System Health
  console.log('📊 System Health:');
  await testEndpoint(`${baseURL}/health`, '  Health Check');
  await testEndpoint(`${baseURL}/api/test-db`, '  Database Connection');
  
  // Credits System (Previously 404)
  console.log('\n💳 Credits System:');
  await testEndpoint(`${baseURL}/api/v1/credits/balance`, '  Credits Balance');
  await testEndpoint(`${baseURL}/api/v1/credits/pricing`, '  Credits Pricing');
  await testEndpoint(`${baseURL}/api/v1/credits/dashboard`, '  Credits Dashboard');
  await testEndpoint(`${baseURL}/api/v1/credits/allowances`, '  Credits Allowances');
  
  // Campaigns System
  console.log('\n📊 Campaigns System:');
  await testEndpoint(`${baseURL}/api/v1/campaigns/`, '  Campaigns List');
  await testEndpoint(`${baseURL}/api/v1/campaigns/user/stats`, '  Campaign Stats');
  
  // Discovery System  
  console.log('\n🔎 Discovery System:');
  await testEndpoint(`${baseURL}/api/v1/discovery/search?query=fitness&limit=5`, '  Discovery Search');
  
  // Instagram Analysis
  console.log('\n📱 Instagram Analysis:');
  await testEndpoint(`${baseURL}/api/instagram/profile/cristiano`, '  Profile Analysis');
  
  // AI System
  console.log('\n🤖 AI System:');
  await testEndpoint(`${baseURL}/api/ai/status`, '  AI Status');
  await testEndpoint(`${baseURL}/api/ai/fix`, '  AI Fix');
  
  // Performance
  console.log('\n⚡ Performance:');
  await testEndpoint(`${baseURL}/api/metrics`, '  System Metrics');
  
  console.log('\n✅ Test completed!');
}

runTests().catch(console.error);