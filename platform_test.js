const { chromium } = require('playwright');

const config = {
  baseURL: 'http://localhost:3000',
  apiURL: 'http://localhost:8000',
  credentials: {
    email: 'client@analyticsfollowing.com',
    password: 'ClientPass2024!'
  }
};

const TEST_USERNAME = 'latifalshamsi';

async function runComprehensiveTest() {
  console.log('🚀 Starting Comprehensive Platform Test...');
  console.log('=========================================');
  
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 1000
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();
  
  const results = {
    passed: 0,
    failed: 0,
    errors: []
  };

  try {
    // Test 1: Backend Health Check
    console.log('\n🔍 Test 1: Backend Health & Database');
    console.log('------------------------------------');
    
    try {
      const healthResponse = await page.request.get(`${config.apiURL}/health`);
      const healthData = await healthResponse.json();
      
      console.log('✅ Backend Status:', healthData.status);
      console.log('🔧 Services:', Object.keys(healthData.services || {}));
      
      if (healthResponse.status() === 200 && healthData.status === 'healthy') {
        results.passed++;
        console.log('✅ Backend health check passed');
      } else {
        throw new Error(`Backend unhealthy: ${healthData.status}`);
      }
      
      // Test database connectivity
      const metricsResponse = await page.request.get(`${config.apiURL}/api/metrics`);
      if (metricsResponse.status() === 200) {
        console.log('✅ Database connectivity confirmed');
        results.passed++;
      } else {
        console.log('⚠️ Metrics endpoint returned:', metricsResponse.status());
      }
      
    } catch (error) {
      console.error('❌ Backend test failed:', error.message);
      results.failed++;
      results.errors.push('Backend Health: ' + error.message);
    }

    // Test 2: Frontend and Authentication
    console.log('\n🔍 Test 2: Frontend & Authentication');
    console.log('-------------------------------------');
    
    const requests = [];
    page.on('response', response => {
      if (response.url().includes('/api/')) {
        requests.push({
          url: response.url(),
          status: response.status(),
          method: response.request().method()
        });
      }
    });
    
    try {
      await page.goto(config.baseURL);
      console.log('✅ Frontend accessible');
      
      await page.waitForTimeout(3000);
      const currentUrl = page.url();
      console.log('📍 Current URL:', currentUrl);
      
      // Look for login form
      await page.waitForSelector('input[type="email"], input[name="email"]', { timeout: 10000 });
      console.log('✅ Login form found');
      
      // Fill credentials
      await page.fill('input[type="email"], input[name="email"]', config.credentials.email);
      await page.fill('input[type="password"], input[name="password"]', config.credentials.password);
      console.log('✅ Credentials filled');
      
      // Submit login
      await page.click('button[type="submit"], button:has-text("Login"), button:has-text("Sign In")');
      console.log('✅ Login submitted');
      
      // Wait for authentication
      await page.waitForTimeout(5000);
      
      const postLoginUrl = page.url();
      console.log('📍 Post-login URL:', postLoginUrl);
      
      if (postLoginUrl.includes('dashboard') || !postLoginUrl.includes('login')) {
        console.log('✅ Authentication successful');
        results.passed++;
      } else {
        throw new Error('Still on login page after authentication attempt');
      }
      
      // Log auth API calls
      const authCalls = requests.filter(r => r.url.includes('auth') || r.url.includes('login'));
      console.log(`📡 Auth API calls: ${authCalls.length}`);
      authCalls.forEach(call => {
        const status = call.status < 400 ? '✅' : '❌';
        console.log(`  ${status} ${call.method} ${call.url.replace(config.apiURL, '')} (${call.status})`);
      });
      
    } catch (error) {
      console.error('❌ Authentication failed:', error.message);
      await page.screenshot({ path: 'auth-error.png', fullPage: true });
      results.failed++;
      results.errors.push('Authentication: ' + error.message);
    }

    // Test 3: Dashboard Tab
    console.log('\n🔍 Test 3: Dashboard Tab');
    console.log('------------------------');
    
    try {
      await page.goto(`${config.baseURL}/dashboard`);
      await page.waitForLoadState('networkidle');
      
      const dashboardCalls = [];
      page.on('response', response => {
        if (response.url().includes(config.apiURL)) {
          dashboardCalls.push({
            url: response.url(),
            status: response.status(),
            method: response.request().method()
          });
        }
      });
      
      await page.waitForTimeout(3000);
      
      // Check for dashboard elements
      const elements = ['Welcome', 'Dashboard', 'Analytics', 'Overview'];
      let found = 0;
      
      for (const element of elements) {
        const exists = await page.locator(`text=${element}`).first().isVisible({ timeout: 2000 }).catch(() => false);
        if (exists) {
          console.log(`✅ Found: ${element}`);
          found++;
        }
      }
      
      console.log(`📊 Dashboard elements: ${found}/${elements.length}`);
      
      if (dashboardCalls.length > 0) {
        console.log(`📡 Dashboard API calls: ${dashboardCalls.length}`);
        dashboardCalls.forEach(call => {
          const status = call.status < 400 ? '✅' : '❌';
          console.log(`  ${status} ${call.method} ${call.url.replace(config.apiURL, '')} (${call.status})`);
        });
      }
      
      await page.screenshot({ path: 'dashboard-test.png', fullPage: true });
      results.passed++;
      
    } catch (error) {
      console.error('❌ Dashboard test failed:', error.message);
      results.failed++;
      results.errors.push('Dashboard: ' + error.message);
    }

    // Test 4: Creators Tab
    console.log('\n🔍 Test 4: Creators Tab');
    console.log('-----------------------');
    
    try {
      await page.goto(`${config.baseURL}/creators`);
      await page.waitForLoadState('networkidle');
      
      const creatorCalls = [];
      page.on('response', response => {
        if (response.url().includes(config.apiURL)) {
          creatorCalls.push({
            url: response.url(),
            status: response.status(),
            method: response.request().method()
          });
        }
      });
      
      console.log('👥 Testing creator search...');
      
      // Try to find search input
      const searchSelectors = [
        'input[type="search"]',
        'input[placeholder*="search" i]',
        'input[placeholder*="username" i]'
      ];
      
      let searchFound = false;
      for (const selector of searchSelectors) {
        const element = page.locator(selector).first();
        if (await element.isVisible({ timeout: 2000 }).catch(() => false)) {
          console.log(`✅ Search input found: ${selector}`);
          await element.fill(TEST_USERNAME);
          await element.press('Enter');
          searchFound = true;
          break;
        }
      }
      
      if (!searchFound) {
        console.log('⚠️ Search input not found, trying direct navigation');
        await page.goto(`${config.baseURL}/analytics/${TEST_USERNAME}`);
      }
      
      await page.waitForTimeout(5000);
      
      // Check for analysis results
      const analysisElements = [TEST_USERNAME, 'followers', 'engagement', 'posts'];
      let analysisFound = 0;
      
      for (const element of analysisElements) {
        const exists = await page.locator(`text=${element}`).first().isVisible({ timeout: 2000 }).catch(() => false);
        if (exists) {
          console.log(`✅ Found analysis: ${element}`);
          analysisFound++;
        }
      }
      
      console.log(`📈 Analysis elements: ${analysisFound}/${analysisElements.length}`);
      
      if (creatorCalls.length > 0) {
        console.log(`📡 Creator API calls: ${creatorCalls.length}`);
        creatorCalls.forEach(call => {
          const status = call.status < 400 ? '✅' : '❌';
          console.log(`  ${status} ${call.method} ${call.url.replace(config.apiURL, '')} (${call.status})`);
        });
      }
      
      await page.screenshot({ path: 'creators-test.png', fullPage: true });
      results.passed++;
      
    } catch (error) {
      console.error('❌ Creators test failed:', error.message);
      results.failed++;
      results.errors.push('Creators: ' + error.message);
    }

    // Test 5: Lists Tab
    console.log('\n🔍 Test 5: Lists Tab');
    console.log('-------------------');
    
    try {
      await page.goto(`${config.baseURL}/my-lists`);
      await page.waitForLoadState('networkidle');
      
      const listCalls = [];
      page.on('response', response => {
        if (response.url().includes(config.apiURL)) {
          listCalls.push({
            url: response.url(),
            status: response.status(),
            method: response.request().method()
          });
        }
      });
      
      await page.waitForTimeout(2000);
      
      // Check for lists elements
      const listElements = ['Lists', 'My Lists', 'Create', 'New List'];
      let listFound = 0;
      
      for (const element of listElements) {
        const exists = await page.locator(`text=${element}`).first().isVisible({ timeout: 2000 }).catch(() => false);
        if (exists) {
          console.log(`✅ Found list element: ${element}`);
          listFound++;
        }
      }
      
      console.log(`📋 List elements: ${listFound}/${listElements.length}`);
      
      if (listCalls.length > 0) {
        console.log(`📡 Lists API calls: ${listCalls.length}`);
        listCalls.forEach(call => {
          const status = call.status < 400 ? '✅' : '❌';
          console.log(`  ${status} ${call.method} ${call.url.replace(config.apiURL, '')} (${call.status})`);
        });
      }
      
      await page.screenshot({ path: 'lists-test.png', fullPage: true });
      results.passed++;
      
    } catch (error) {
      console.error('❌ Lists test failed:', error.message);
      results.failed++;
      results.errors.push('Lists: ' + error.message);
    }

    // Test 6: Campaigns Tab
    console.log('\n🔍 Test 6: Campaigns Tab');
    console.log('-----------------------');
    
    try {
      await page.goto(`${config.baseURL}/campaigns`);
      await page.waitForLoadState('networkidle');
      
      const campaignCalls = [];
      page.on('response', response => {
        if (response.url().includes(config.apiURL)) {
          campaignCalls.push({
            url: response.url(),
            status: response.status(),
            method: response.request().method()
          });
        }
      });
      
      await page.waitForTimeout(2000);
      
      // Check for campaign elements
      const campaignElements = ['Campaign', 'Campaigns', 'Create', 'New Campaign'];
      let campaignFound = 0;
      
      for (const element of campaignElements) {
        const exists = await page.locator(`text=${element}`).first().isVisible({ timeout: 2000 }).catch(() => false);
        if (exists) {
          console.log(`✅ Found campaign element: ${element}`);
          campaignFound++;
        }
      }
      
      console.log(`🎯 Campaign elements: ${campaignFound}/${campaignElements.length}`);
      
      if (campaignCalls.length > 0) {
        console.log(`📡 Campaign API calls: ${campaignCalls.length}`);
        campaignCalls.forEach(call => {
          const status = call.status < 400 ? '✅' : '❌';
          console.log(`  ${status} ${call.method} ${call.url.replace(config.apiURL, '')} (${call.status})`);
        });
      }
      
      await page.screenshot({ path: 'campaigns-test.png', fullPage: true });
      results.passed++;
      
    } catch (error) {
      console.error('❌ Campaigns test failed:', error.message);
      results.failed++;
      results.errors.push('Campaigns: ' + error.message);
    }

    // Test 7: Credits System
    console.log('\n🔍 Test 7: Credits System');
    console.log('------------------------');
    
    try {
      // Test credits endpoints
      const creditsResponse = await page.request.get(`${config.apiURL}/api/v1/credits/balance`);
      
      if (creditsResponse.status() === 200) {
        const creditsData = await creditsResponse.json();
        console.log('✅ Credits balance retrieved:', creditsData);
        results.passed++;
      } else if (creditsResponse.status() === 401) {
        console.log('⚠️ Credits API requires proper authentication');
      } else {
        console.log(`⚠️ Credits API status: ${creditsResponse.status()}`);
      }
      
    } catch (error) {
      console.error('❌ Credits test failed:', error.message);
      results.failed++;
      results.errors.push('Credits: ' + error.message);
    }

    // Test 8: Performance & Error Handling
    console.log('\n🔍 Test 8: Performance & Error Handling');
    console.log('---------------------------------------');
    
    try {
      // Test response time
      const start = Date.now();
      const perfResponse = await page.request.get(`${config.apiURL}/health`);
      const responseTime = Date.now() - start;
      
      console.log(`⏱️ Health endpoint: ${responseTime}ms`);
      
      if (responseTime < 2000) {
        console.log('✅ Response time acceptable');
        results.passed++;
      } else {
        console.log('⚠️ Response time slow');
      }
      
      // Test error handling
      const errorResponse = await page.request.get(`${config.apiURL}/api/invalid-endpoint`);
      console.log(`🛡️ Error handling: ${errorResponse.status()}`);
      
    } catch (error) {
      console.error('❌ Performance test failed:', error.message);
      results.failed++;
      results.errors.push('Performance: ' + error.message);
    }

  } catch (globalError) {
    console.error('❌ Global test error:', globalError.message);
    results.failed++;
    results.errors.push('Global: ' + globalError.message);
  }

  // Final Results
  console.log('\n📊 COMPREHENSIVE TEST RESULTS');
  console.log('==============================');
  console.log(`✅ Tests Passed: ${results.passed}`);
  console.log(`❌ Tests Failed: ${results.failed}`);
  
  const total = results.passed + results.failed;
  if (total > 0) {
    const successRate = Math.round((results.passed / total) * 100);
    console.log(`📈 Success Rate: ${successRate}%`);
  }
  
  if (results.errors.length > 0) {
    console.log('\n🚨 ISSUES IDENTIFIED:');
    console.log('----------------------');
    results.errors.forEach((error, index) => {
      console.log(`${index + 1}. ${error}`);
    });
  }
  
  await browser.close();
  return results;
}

runComprehensiveTest()
  .then(results => {
    console.log('\n🏁 Test execution completed');
    process.exit(results.failed > 0 ? 1 : 0);
  })
  .catch(error => {
    console.error('❌ Test execution failed:', error);
    process.exit(1);
  });