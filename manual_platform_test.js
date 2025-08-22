const { chromium } = require('playwright');

async function manualPlatformTest() {
  console.log('🚀 Starting Manual Platform Verification...');
  console.log('============================================');
  
  const browser = await chromium.launch({ 
    headless: false, // Show browser for manual verification
    slowMo: 2000 // Slow down for better observation
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();
  
  // Monitor all network requests
  const apiCalls = [];
  const errors = [];
  
  page.on('response', response => {
    if (response.url().includes('/api/')) {
      apiCalls.push({
        url: response.url(),
        status: response.status(),
        method: response.request().method(),
        timestamp: new Date().toISOString()
      });
      
      if (response.status() >= 400) {
        errors.push({
          url: response.url(),
          status: response.status(),
          statusText: response.statusText()
        });
      }
    }
  });
  
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('🔥 Browser Console Error:', msg.text());
      errors.push({
        type: 'console_error',
        message: msg.text()
      });
    }
  });
  
  try {
    // Step 1: Login
    console.log('\n📝 Step 1: Login Process');
    console.log('------------------------');
    
    await page.goto('http://localhost:3000');
    console.log('✅ Navigated to frontend');
    
    // Wait for page to load and take screenshot
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'step1-login-page.png', fullPage: true });
    console.log('📸 Screenshot: step1-login-page.png');
    
    // Fill login credentials
    await page.waitForSelector('input[type="email"], input[name="email"]', { timeout: 10000 });
    await page.fill('input[type="email"], input[name="email"]', 'client@analyticsfollowing.com');
    await page.fill('input[type="password"], input[name="password"]', 'ClientPass2024!');
    
    await page.screenshot({ path: 'step2-form-filled.png', fullPage: true });
    console.log('📸 Screenshot: step2-form-filled.png');
    
    // Submit login
    await page.click('button[type="submit"], button:has-text("Login"), button:has-text("Sign In")');
    console.log('✅ Login submitted');
    
    // Wait for authentication to complete
    await page.waitForTimeout(5000);
    
    const loginApiCalls = apiCalls.filter(call => call.url.includes('auth') || call.url.includes('login'));
    console.log(`📡 Login API calls: ${loginApiCalls.length}`);
    loginApiCalls.forEach(call => {
      console.log(`  - ${call.method} ${call.url} (${call.status}) at ${call.timestamp}`);
    });
    
    // Step 2: Dashboard Page
    console.log('\n📊 Step 2: Dashboard Page');
    console.log('-------------------------');
    
    await page.goto('http://localhost:3000/dashboard');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    await page.screenshot({ path: 'step3-dashboard.png', fullPage: true });
    console.log('📸 Screenshot: step3-dashboard.png');
    
    const dashboardApiCalls = apiCalls.filter(call => 
      call.timestamp > (loginApiCalls[loginApiCalls.length - 1]?.timestamp || '')
    );
    console.log(`📡 Dashboard API calls: ${dashboardApiCalls.length}`);
    dashboardApiCalls.forEach(call => {
      const status = call.status < 400 ? '✅' : '❌';
      console.log(`  ${status} ${call.method} ${call.url.replace('http://localhost:8000', '')} (${call.status})`);
    });
    
    // Step 3: Creators Page
    console.log('\n👥 Step 3: Creators Page');
    console.log('------------------------');
    
    const beforeCreators = apiCalls.length;
    await page.goto('http://localhost:3000/creators');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    await page.screenshot({ path: 'step4-creators.png', fullPage: true });
    console.log('📸 Screenshot: step4-creators.png');
    
    // Try to perform a search
    try {
      const searchInput = page.locator('input[type="search"], input[placeholder*="search" i]').first();
      if (await searchInput.isVisible({ timeout: 3000 })) {
        await searchInput.fill('latifalshamsi');
        await searchInput.press('Enter');
        console.log('🔍 Performed creator search for: latifalshamsi');
        
        await page.waitForTimeout(5000);
        await page.screenshot({ path: 'step4b-creator-search.png', fullPage: true });
        console.log('📸 Screenshot: step4b-creator-search.png');
      }
    } catch (e) {
      console.log('⚠️ Creator search not available or failed:', e.message);
    }
    
    const creatorsApiCalls = apiCalls.slice(beforeCreators);
    console.log(`📡 Creators API calls: ${creatorsApiCalls.length}`);
    creatorsApiCalls.forEach(call => {
      const status = call.status < 400 ? '✅' : '❌';
      console.log(`  ${status} ${call.method} ${call.url.replace('http://localhost:8000', '')} (${call.status})`);
    });
    
    // Step 4: Billing Page
    console.log('\n💳 Step 4: Billing Page');
    console.log('-----------------------');
    
    const beforeBilling = apiCalls.length;
    await page.goto('http://localhost:3000/billing');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    await page.screenshot({ path: 'step5-billing.png', fullPage: true });
    console.log('📸 Screenshot: step5-billing.png');
    
    const billingApiCalls = apiCalls.slice(beforeBilling);
    console.log(`📡 Billing API calls: ${billingApiCalls.length}`);
    billingApiCalls.forEach(call => {
      const status = call.status < 400 ? '✅' : '❌';
      console.log(`  ${status} ${call.method} ${call.url.replace('http://localhost:8000', '')} (${call.status})`);
    });
    
    // Step 5: Lists Page
    console.log('\n📝 Step 5: Lists/My-Lists Page');
    console.log('------------------------------');
    
    const beforeLists = apiCalls.length;
    await page.goto('http://localhost:3000/my-lists');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    await page.screenshot({ path: 'step6-lists.png', fullPage: true });
    console.log('📸 Screenshot: step6-lists.png');
    
    const listsApiCalls = apiCalls.slice(beforeLists);
    console.log(`📡 Lists API calls: ${listsApiCalls.length}`);
    listsApiCalls.forEach(call => {
      const status = call.status < 400 ? '✅' : '❌';
      console.log(`  ${status} ${call.method} ${call.url.replace('http://localhost:8000', '')} (${call.status})`);
    });
    
    // Step 6: Campaigns Page
    console.log('\n🎯 Step 6: Campaigns Page');
    console.log('-------------------------');
    
    const beforeCampaigns = apiCalls.length;
    await page.goto('http://localhost:3000/campaigns');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    await page.screenshot({ path: 'step7-campaigns.png', fullPage: true });
    console.log('📸 Screenshot: step7-campaigns.png');
    
    const campaignsApiCalls = apiCalls.slice(beforeCampaigns);
    console.log(`📡 Campaigns API calls: ${campaignsApiCalls.length}`);
    campaignsApiCalls.forEach(call => {
      const status = call.status < 400 ? '✅' : '❌';
      console.log(`  ${status} ${call.method} ${call.url.replace('http://localhost:8000', '')} (${call.status})`);
    });
    
    // Final Summary
    console.log('\n📊 MANUAL VERIFICATION SUMMARY');
    console.log('==============================');
    console.log(`📡 Total API calls made: ${apiCalls.length}`);
    console.log(`❌ Backend errors found: ${errors.length}`);
    
    if (errors.length > 0) {
      console.log('\n🚨 BACKEND ISSUES DETECTED:');
      console.log('---------------------------');
      errors.forEach((error, index) => {
        console.log(`${index + 1}. ${error.type || 'HTTP Error'}: ${error.url || error.message} - ${error.status || ''} ${error.statusText || ''}`);
      });
    } else {
      console.log('\n✅ NO BACKEND ISSUES DETECTED');
      console.log('All pages loaded successfully with no errors!');
    }
    
    // Log all API calls by page
    console.log('\n📋 API CALLS BY PAGE:');
    console.log('---------------------');
    
    const pageGroups = {
      'Login/Auth': apiCalls.filter(call => call.url.includes('auth') || call.url.includes('login')),
      'Dashboard': dashboardApiCalls,
      'Creators': creatorsApiCalls, 
      'Billing': billingApiCalls,
      'Lists': listsApiCalls,
      'Campaigns': campaignsApiCalls
    };
    
    Object.entries(pageGroups).forEach(([page, calls]) => {
      console.log(`\n${page} (${calls.length} calls):`);
      calls.forEach(call => {
        const status = call.status < 400 ? '✅' : '❌';
        console.log(`  ${status} ${call.method} ${call.url.replace('http://localhost:8000', '')} (${call.status})`);
      });
    });
    
    console.log('\n⏰ Browser will remain open for 30 seconds for manual inspection...');
    await page.waitForTimeout(30000);
    
  } catch (error) {
    console.error('❌ Manual test failed:', error.message);
    await page.screenshot({ path: 'error-state.png', fullPage: true });
    console.log('📸 Error screenshot: error-state.png');
  }
  
  await browser.close();
  
  return {
    totalApiCalls: apiCalls.length,
    errors: errors,
    success: errors.length === 0
  };
}

manualPlatformTest()
  .then(results => {
    console.log('\n🏁 Manual verification completed');
    console.log(`Result: ${results.success ? 'SUCCESS' : 'ISSUES FOUND'}`);
    process.exit(results.errors.length > 0 ? 1 : 0);
  })
  .catch(error => {
    console.error('❌ Manual test execution failed:', error);
    process.exit(1);
  });