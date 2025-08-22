const https = require('http');

async function testEndpoint(url, description) {
  return new Promise((resolve) => {
    const req = https.get(url, (res) => {
      let status_symbol = '';
      if (res.statusCode === 200) status_symbol = '✅';
      else if (res.statusCode === 401 || res.statusCode === 403) status_symbol = '🔒';
      else if (res.statusCode === 404) status_symbol = '❌';
      else status_symbol = '⚠️';
      
      console.log(`${status_symbol} ${description}: ${res.statusCode}`);
      resolve(res.statusCode);
    });
    
    req.on('error', (error) => {
      console.log(`❌ ${description}: ERROR - ${error.message}`);
      resolve(null);
    });
    
    req.setTimeout(3000, () => {
      req.destroy();
      console.log(`⏱️ ${description}: TIMEOUT`);
      resolve(null);
    });
  });
}

async function runFinalVerification() {
  console.log('🔍 FINAL SYSTEM VERIFICATION REPORT\n');
  
  const baseURL = 'http://localhost:8000';
  
  // System Health
  console.log('📊 SYSTEM HEALTH & CORE:');
  await testEndpoint(`${baseURL}/health`, '  Main Health Check');
  await testEndpoint(`${baseURL}/api/v1/health`, '  API Health Check');
  await testEndpoint(`${baseURL}/api/v1/status`, '  API Status');
  
  // Credits System (FIXED - now returning 403 instead of 404)
  console.log('\n💳 CREDITS SYSTEM (Fixed - Previously 404):');
  await testEndpoint(`${baseURL}/api/v1/credits/balance`, '  Credits Balance');
  await testEndpoint(`${baseURL}/api/v1/credits/pricing`, '  Credits Pricing');
  await testEndpoint(`${baseURL}/api/v1/credits/dashboard`, '  Credits Dashboard');
  
  // Instagram Analysis (Corrected Path)
  console.log('\n📱 INSTAGRAM ANALYSIS (Corrected Path):');
  await testEndpoint(`${baseURL}/api/v1/instagram/profile/cristiano`, '  Profile Analysis');
  await testEndpoint(`${baseURL}/api/v1/instagram/profile/cristiano/analytics`, '  Profile Analytics');
  await testEndpoint(`${baseURL}/api/v1/search/suggestions/cris`, '  Username Suggestions');
  
  // AI System (Corrected Path)
  console.log('\n🤖 AI SYSTEM (Corrected Path):');
  await testEndpoint(`${baseURL}/api/v1/ai/system/health`, '  AI System Health');
  await testEndpoint(`${baseURL}/api/v1/ai/analysis/status`, '  AI Analysis Status');
  
  // Auth System
  console.log('\n🔐 AUTHENTICATION SYSTEM:');
  await testEndpoint(`${baseURL}/api/v1/auth/health`, '  Auth Health');
  
  // Check Missing Systems
  console.log('\n❓ SYSTEMS TO BE VERIFIED (May be missing):');
  await testEndpoint(`${baseURL}/api/v1/campaigns/`, '  Campaigns System');
  await testEndpoint(`${baseURL}/api/v1/discovery/search?query=test`, '  Discovery System');
  
  console.log('\n📋 VERIFICATION SUMMARY:');
  console.log('✅ = Working (200)');
  console.log('🔒 = Requires Auth (401/403) - Expected');
  console.log('❌ = Not Found (404) - Issue');
  console.log('⚠️ = Other Status - Needs Investigation');
  console.log('⏱️ = Timeout - Server Issue\n');
}

runFinalVerification().catch(console.error);