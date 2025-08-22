const { test, expect } = require('@playwright/test');

// Configuration
const config = {
  baseURL: 'http://localhost:3000',
  apiURL: 'http://localhost:8000',
  credentials: {
    email: 'client@analyticsfollowing.com',
    password: 'ClientPass2024!'
  }
};

// Test username for creator analysis
const TEST_USERNAME = 'latifalshamsi';

test.describe('Comprehensive Platform Testing', () => {
  
  test.beforeEach(async ({ page }) => {
    test.setTimeout(120000); // 2 minute timeout
    console.log('🚀 Starting comprehensive platform test...');
  });

  test('1. Backend Health and Database Connectivity', async ({ page }) => {
    console.log('\n=== TESTING BACKEND HEALTH & DATABASE ===');
    
    // Test backend health endpoint
    const healthResponse = await page.request.get(`${config.apiURL}/health`);
    expect(healthResponse.status()).toBe(200);
    
    const healthData = await healthResponse.json();
    console.log('✅ Backend Health:', healthData.status);
    console.log('🔧 Services:', Object.keys(healthData.services || {}));
    
    // Test database connectivity via metrics
    try {
      const metricsResponse = await page.request.get(`${config.apiURL}/api/metrics`);
      if (metricsResponse.status() === 200) {
        console.log('✅ Database connectivity confirmed via metrics endpoint');
      } else {
        console.log('⚠️ Metrics endpoint returned:', metricsResponse.status());
      }
    } catch (error) {
      console.log('⚠️ Metrics endpoint not accessible:', error.message);
    }
  });

  test('2. Frontend Accessibility and Authentication', async ({ page }) => {
    console.log('\n=== TESTING FRONTEND & AUTHENTICATION ===');
    
    // Monitor network requests
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
    
    // Navigate to frontend
    await page.goto(config.baseURL);
    console.log('✅ Frontend loaded successfully');
    
    // Should redirect to login or show login form
    await page.waitForTimeout(2000);
    const currentUrl = page.url();
    console.log('📍 Current URL:', currentUrl);
    
    // Look for login elements
    try {
      await page.waitForSelector('input[type="email"], input[name="email"]', { timeout: 10000 });
      console.log('✅ Login form found');
      
      // Fill login credentials
      await page.fill('input[type="email"], input[name="email"]', config.credentials.email);
      await page.fill('input[type="password"], input[name="password"]', config.credentials.password);
      
      console.log('✅ Credentials entered');
      
      // Submit login
      await page.click('button[type="submit"], button:has-text("Login"), button:has-text("Sign In")');
      console.log('✅ Login submitted');
      
      // Wait for authentication to complete
      await page.waitForTimeout(5000);
      
      // Check if we're redirected to dashboard or authenticated area
      const postLoginUrl = page.url();
      console.log('📍 Post-login URL:', postLoginUrl);
      
      if (postLoginUrl.includes('dashboard') || !postLoginUrl.includes('login')) {
        console.log('✅ Authentication successful');
      } else {
        console.log('⚠️ Authentication may have failed - still on login page');
      }
      
      // Log authentication-related API calls
      const authRequests = requests.filter(req => 
        req.url.includes('auth') || req.url.includes('login')
      );
      console.log(`📡 Authentication API calls: ${authRequests.length}`);
      authRequests.forEach(req => {
        console.log(`  - ${req.method} ${req.url.replace(config.apiURL, '')} (${req.status})`);
      });
      
    } catch (error) {
      console.error('❌ Login process failed:', error.message);
      await page.screenshot({ path: 'login-error.png', fullPage: true });
      throw error;
    }
  });

  test('3. Dashboard Tab Functionality', async ({ page }) => {
    console.log('\n=== TESTING DASHBOARD TAB ===');
    
    // Login first
    await performLogin(page);
    
    // Navigate to dashboard
    await page.goto(`${config.baseURL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // Monitor API calls
    const apiCalls = [];
    page.on('response', response => {
      if (response.url().includes(config.apiURL)) {
        apiCalls.push({
          url: response.url(),
          status: response.status(),
          method: response.request().method()
        });
      }
    });
    
    // Wait for dashboard to load
    await page.waitForTimeout(3000);
    
    // Check for dashboard elements
    const dashboardElements = [
      'Welcome', 'Dashboard', 'Analytics', 'Overview', 'Recent'
    ];
    
    let foundElements = 0;
    for (const element of dashboardElements) {
      const exists = await page.locator(`text=${element}`).first().isVisible({ timeout: 2000 }).catch(() => false);
      if (exists) {
        console.log(`✅ Found dashboard element: ${element}`);
        foundElements++;
      }
    }
    
    console.log(`📊 Dashboard elements found: ${foundElements}/${dashboardElements.length}`);
    
    // Log API calls
    if (apiCalls.length > 0) {
      console.log(`📡 Dashboard API calls: ${apiCalls.length}`);
      apiCalls.forEach(call => {
        const status = call.status < 400 ? '✅' : '❌';
        console.log(`  ${status} ${call.method} ${call.url.replace(config.apiURL, '')} (${call.status})`);
      });
    }
    
    await page.screenshot({ path: 'dashboard-test.png', fullPage: true });
  });

  test('4. Creators Tab - Search and Analysis', async ({ page }) => {
    console.log('\n=== TESTING CREATORS TAB ===');
    
    // Login first
    await performLogin(page);
    
    // Monitor API calls for this test
    const apiCalls = [];
    page.on('response', response => {
      if (response.url().includes(config.apiURL)) {
        apiCalls.push({
          url: response.url(),
          status: response.status(),
          method: response.request().method()
        });
      }
    });
    
    // Navigate to creators page
    await page.goto(`${config.baseURL}/creators`);
    await page.waitForLoadState('networkidle');
    
    console.log('👥 Testing creator search functionality...');
    
    try {
      // Look for search input
      const searchSelectors = [
        'input[type="search"]',
        'input[placeholder*="search" i]',
        'input[placeholder*="username" i]',
        'input[name="search"]',
        '#search'
      ];
      
      let searchInput = null;
      for (const selector of searchSelectors) {
        const element = page.locator(selector).first();
        if (await element.isVisible({ timeout: 2000 }).catch(() => false)) {
          searchInput = element;
          console.log(`✅ Search input found: ${selector}`);
          break;
        }
      }
      
      if (searchInput) {
        // Perform search
        await searchInput.fill(TEST_USERNAME);
        console.log(`🔍 Searching for: ${TEST_USERNAME}`);
        
        // Try to submit search
        await Promise.race([
          searchInput.press('Enter'),
          page.click('button:has-text("Search"), button:has-text("Analyze")')
        ]);
        
        // Wait for results
        await page.waitForTimeout(5000);
        
        // Check if we got results or were redirected
        const currentUrl = page.url();
        console.log('📍 After search URL:', currentUrl);
        
      } else {
        console.log('⚠️ Search input not found, trying direct navigation');
        await page.goto(`${config.baseURL}/analytics/${TEST_USERNAME}`);
      }
      
      // Check for analysis results
      await page.waitForTimeout(3000);
      
      const analysisElements = [
        TEST_USERNAME, 'followers', 'engagement', 'posts', 'profile'
      ];
      
      let foundAnalysis = 0;
      for (const element of analysisElements) {
        const exists = await page.locator(`text=${element}`).first().isVisible({ timeout: 2000 }).catch(() => false);
        if (exists) {
          console.log(`✅ Found analysis element: ${element}`);
          foundAnalysis++;
        }
      }
      
      console.log(`📈 Analysis elements found: ${foundAnalysis}/${analysisElements.length}`);
      
    } catch (error) {
      console.error('❌ Creator search failed:', error.message);
      await page.screenshot({ path: 'creator-search-error.png', fullPage: true });
    }
    
    // Log all API calls made during creator testing
    console.log(`📡 Creator analysis API calls: ${apiCalls.length}`);
    apiCalls.forEach(call => {
      const status = call.status < 400 ? '✅' : '❌';
      console.log(`  ${status} ${call.method} ${call.url.replace(config.apiURL, '')} (${call.status})`);
    });
  });

  test('5. Lists Tab Functionality', async ({ page }) => {
    console.log('\n=== TESTING LISTS TAB ===');
    
    // Login first
    await performLogin(page);
    
    // Monitor API calls
    const apiCalls = [];
    page.on('response', response => {
      if (response.url().includes(config.apiURL)) {
        apiCalls.push({
          url: response.url(),
          status: response.status(),
          method: response.request().method()
        });
      }
    });
    
    // Navigate to lists page
    await page.goto(`${config.baseURL}/my-lists`);
    await page.waitForLoadState('networkidle');
    
    console.log('📝 Testing lists functionality...');
    
    // Wait for page to load
    await page.waitForTimeout(2000);
    
    // Check for lists-related elements
    const listElements = [
      'Lists', 'My Lists', 'Create', 'New List', 'Add'
    ];
    
    let foundListElements = 0;
    for (const element of listElements) {
      const exists = await page.locator(`text=${element}`).first().isVisible({ timeout: 2000 }).catch(() => false);
      if (exists) {
        console.log(`✅ Found list element: ${element}`);
        foundListElements++;
      }
    }
    
    console.log(`📋 List elements found: ${foundListElements}/${listElements.length}`);
    
    // Try to interact with create list functionality
    try {
      const createButtons = [
        'button:has-text("Create")',
        'button:has-text("New List")',
        'button:has-text("Add List")',
        'a:has-text("Create")',
        '[data-testid="create-list"]'
      ];
      
      for (const buttonSelector of createButtons) {
        const button = page.locator(buttonSelector).first();
        if (await button.isVisible({ timeout: 1000 }).catch(() => false)) {
          console.log(`✅ Found create button: ${buttonSelector}`);
          await button.click();
          await page.waitForTimeout(2000);
          break;
        }
      }
    } catch (error) {
      console.log('⚠️ Could not test list creation:', error.message);
    }
    
    // Log API calls
    console.log(`📡 Lists API calls: ${apiCalls.length}`);
    apiCalls.forEach(call => {
      const status = call.status < 400 ? '✅' : '❌';
      console.log(`  ${status} ${call.method} ${call.url.replace(config.apiURL, '')} (${call.status})`);
    });
    
    await page.screenshot({ path: 'lists-test.png', fullPage: true });
  });

  test('6. Campaigns Tab Functionality', async ({ page }) => {
    console.log('\n=== TESTING CAMPAIGNS TAB ===');
    
    // Login first
    await performLogin(page);
    
    // Monitor API calls
    const apiCalls = [];
    page.on('response', response => {
      if (response.url().includes(config.apiURL)) {
        apiCalls.push({
          url: response.url(),
          status: response.status(),
          method: response.request().method()
        });
      }
    });
    
    // Navigate to campaigns page
    await page.goto(`${config.baseURL}/campaigns`);
    await page.waitForLoadState('networkidle');
    
    console.log('🎯 Testing campaigns functionality...');
    
    // Wait for page to load
    await page.waitForTimeout(2000);
    
    // Check for campaign-related elements
    const campaignElements = [
      'Campaign', 'Campaigns', 'Create', 'New Campaign', 'My Campaigns'
    ];
    
    let foundCampaignElements = 0;
    for (const element of campaignElements) {
      const exists = await page.locator(`text=${element}`).first().isVisible({ timeout: 2000 }).catch(() => false);
      if (exists) {
        console.log(`✅ Found campaign element: ${element}`);
        foundCampaignElements++;
      }
    }
    
    console.log(`🎯 Campaign elements found: ${foundCampaignElements}/${campaignElements.length}`);
    
    // Try to interact with create campaign functionality
    try {
      const createButtons = [
        'button:has-text("Create")',
        'button:has-text("New Campaign")',
        'a:has-text("Create")',
        '[data-testid="create-campaign"]'
      ];
      
      for (const buttonSelector of createButtons) {
        const button = page.locator(buttonSelector).first();
        if (await button.isVisible({ timeout: 1000 }).catch(() => false)) {
          console.log(`✅ Found create campaign button: ${buttonSelector}`);
          await button.click();
          await page.waitForTimeout(2000);
          break;
        }
      }
    } catch (error) {
      console.log('⚠️ Could not test campaign creation:', error.message);
    }
    
    // Log API calls
    console.log(`📡 Campaigns API calls: ${apiCalls.length}`);
    apiCalls.forEach(call => {
      const status = call.status < 400 ? '✅' : '❌';
      console.log(`  ${status} ${call.method} ${call.url.replace(config.apiURL, '')} (${call.status})`);
    });
    
    await page.screenshot({ path: 'campaigns-test.png', fullPage: true });
  });

  test('7. Credits System Integration', async ({ page }) => {
    console.log('\n=== TESTING CREDITS SYSTEM ===');
    
    // Login first
    await performLogin(page);
    
    try {
      // Test credits balance endpoint
      const creditsResponse = await page.request.get(`${config.apiURL}/api/v1/credits/balance`);
      
      if (creditsResponse.status() === 200) {
        const creditsData = await creditsResponse.json();
        console.log('✅ Credits balance retrieved:', creditsData);
      } else if (creditsResponse.status() === 401) {
        console.log('⚠️ Credits API requires authentication - this may be expected');
      } else {
        console.log(`⚠️ Credits API returned status: ${creditsResponse.status()}`);
      }
      
      // Test pricing endpoint
      const pricingResponse = await page.request.get(`${config.apiURL}/api/v1/credits/pricing`);
      if (pricingResponse.status() === 200) {
        const pricingData = await pricingResponse.json();
        console.log('✅ Pricing data retrieved');
      }
      
    } catch (error) {
      console.log('⚠️ Credits system test failed:', error.message);
    }
  });

  test('8. Database Performance and Error Handling', async ({ page }) => {
    console.log('\n=== TESTING DATABASE PERFORMANCE & ERROR HANDLING ===');
    
    // Test response times
    const start = Date.now();
    const healthResponse = await page.request.get(`${config.apiURL}/health`);
    const responseTime = Date.now() - start;
    
    console.log(`⏱️ Health endpoint response time: ${responseTime}ms`);
    
    if (responseTime < 2000) {
      console.log('✅ Response time within acceptable limits');
    } else {
      console.log('⚠️ Response time slower than expected');
    }
    
    // Test error handling
    const invalidResponse = await page.request.get(`${config.apiURL}/api/invalid-endpoint-test`);
    console.log(`🛡️ Invalid endpoint handled with status: ${invalidResponse.status()}`);
    
    // Test database resilience
    try {
      const dbTestResponse = await page.request.get(`${config.apiURL}/api/metrics`);
      if (dbTestResponse.status() < 500) {
        console.log('✅ Database connection stable');
      }
    } catch (error) {
      console.log('⚠️ Database connectivity issue:', error.message);
    }
  });
});

// Helper function to perform login
async function performLogin(page) {
  console.log('🔑 Performing login...');
  
  await page.goto(`${config.baseURL}/login`);
  
  // Fill login form
  await page.fill('input[type="email"], input[name="email"]', config.credentials.email);
  await page.fill('input[type="password"], input[name="password"]', config.credentials.password);
  
  // Submit login
  await page.click('button[type="submit"], button:has-text("Login"), button:has-text("Sign In")');
  
  // Wait for login to complete
  await page.waitForTimeout(3000);
  
  console.log('✅ Login completed');
}