const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 1500
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();
  
  // Listen for console logs and errors
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('🔴 Console Error:', msg.text());
    }
  });
  
  // Listen for network responses
  page.on('response', response => {
    const url = response.url();
    const status = response.status();
    
    // Log API calls
    if (url.includes('/api/') || url.includes('/auth/')) {
      console.log(`🌐 ${status} ${url}`);
    }
    
    // Log errors
    if (status >= 400) {
      console.log(`❌ ${status} Error: ${url}`);
    }
  });
  
  try {
    console.log('🔍 DEBUG: Detailed authentication flow analysis\n');
    
    // Step 1: Navigate to login
    console.log('📍 Step 1: Navigate to login page...');
    await page.goto('http://localhost:3000/auth/login');
    await page.waitForTimeout(3000);
    
    // Check current state
    console.log('📍 URL after navigation:', page.url());
    
    // Take screenshot of login page
    await page.screenshot({ path: 'debug-1-login-page.png', fullPage: true });
    
    // Check form elements
    const emailInput = page.locator('input[name="email"]');
    const passwordInput = page.locator('input[name="password"]');
    const submitButton = page.locator('button[type="submit"]');
    
    const emailVisible = await emailInput.isVisible();
    const passwordVisible = await passwordInput.isVisible();
    const submitVisible = await submitButton.isVisible();
    
    console.log(`📋 Form elements - Email: ${emailVisible}, Password: ${passwordVisible}, Submit: ${submitVisible}`);
    
    if (!emailVisible || !passwordVisible || !submitVisible) {
      console.log('❌ Login form elements not found properly');
      return;
    }
    
    // Step 2: Fill credentials
    console.log('\n🔐 Step 2: Fill credentials...');
    await emailInput.fill('client@analyticsfollowing.com');
    await passwordInput.fill('ClientPass2024!');
    
    // Verify values were filled
    const emailValue = await emailInput.inputValue();
    const passwordValue = await passwordInput.inputValue();
    
    console.log(`📧 Email filled: "${emailValue}"`);
    console.log(`🔑 Password filled: ${passwordValue ? '[HIDDEN]' : 'EMPTY'}`);
    
    // Take screenshot after filling
    await page.screenshot({ path: 'debug-2-form-filled.png', fullPage: true });
    
    // Step 3: Submit and monitor network
    console.log('\n🚀 Step 3: Submit form and monitor network...');
    
    // Click submit button
    await submitButton.click();
    
    // Wait and monitor what happens
    console.log('⏳ Waiting 8 seconds to see network responses...');
    await page.waitForTimeout(8000);
    
    // Check URL after submission
    const postSubmitUrl = page.url();
    console.log(`📍 URL after submit: ${postSubmitUrl}`);
    
    // Take screenshot after submit
    await page.screenshot({ path: 'debug-3-after-submit.png', fullPage: true });
    
    // Check for any alert/error messages
    const alerts = await page.locator('[role="alert"]').all();
    console.log(`⚠️ Found ${alerts.length} alert messages:`);
    
    for (const alert of alerts) {
      const text = await alert.textContent().catch(() => '');
      const innerHTML = await alert.innerHTML().catch(() => '');
      console.log(`   - Text: "${text}"`);
      console.log(`   - HTML: "${innerHTML}"`);
    }
    
    // Check all form-related elements
    const allInputs = await page.locator('input').all();
    console.log(`\n📋 All input elements (${allInputs.length}):`);
    
    for (let i = 0; i < allInputs.length; i++) {
      const input = allInputs[i];
      const type = await input.getAttribute('type').catch(() => 'unknown');
      const name = await input.getAttribute('name').catch(() => 'no-name');
      const value = await input.inputValue().catch(() => '');
      const required = await input.getAttribute('required').catch(() => null);
      
      console.log(`   ${i + 1}. type="${type}" name="${name}" value="${value}" required="${required}"`);
    }
    
    // Check if there are any validation errors
    const validationErrors = await page.locator('.error, .invalid, .validation-error, input:invalid').all();
    if (validationErrors.length > 0) {
      console.log(`\n⚠️ Found ${validationErrors.length} validation issues:`);
      
      for (const error of validationErrors) {
        const text = await error.textContent().catch(() => '');
        const classList = await error.getAttribute('class').catch(() => '');
        console.log(`   - "${text}" (${classList})`);
      }
    }
    
    // Step 4: Try manual navigation to test session
    console.log('\n🎯 Step 4: Test direct navigation to analytics...');
    await page.goto('http://localhost:3000/analytics/latifalshamsi');
    await page.waitForTimeout(3000);
    
    const finalUrl = page.url();
    console.log(`📍 Final URL: ${finalUrl}`);
    
    await page.screenshot({ path: 'debug-4-direct-navigation.png', fullPage: true });
    
    // Step 5: Try different approach - dashboard first
    console.log('\n🏠 Step 5: Try dashboard navigation...');
    await page.goto('http://localhost:3000/dashboard');
    await page.waitForTimeout(3000);
    
    const dashboardUrl = page.url();
    console.log(`📍 Dashboard URL: ${dashboardUrl}`);
    
    await page.screenshot({ path: 'debug-5-dashboard.png', fullPage: true });
    
    // Step 6: Check cookies and local storage
    console.log('\n🍪 Step 6: Check session data...');
    
    const cookies = await context.cookies();
    console.log(`🍪 Found ${cookies.length} cookies:`);
    cookies.forEach(cookie => {
      console.log(`   - ${cookie.name}: ${cookie.value.slice(0, 20)}...`);
    });
    
    const localStorage = await page.evaluate(() => {
      const items = {};
      for (let i = 0; i < window.localStorage.length; i++) {
        const key = window.localStorage.key(i);
        const value = window.localStorage.getItem(key);
        items[key] = value ? value.slice(0, 50) + '...' : null;
      }
      return items;
    });
    
    console.log('💾 LocalStorage items:');
    Object.entries(localStorage).forEach(([key, value]) => {
      console.log(`   - ${key}: ${value}`);
    });
    
    console.log('\n🎯 === ANALYSIS SUMMARY ===');
    console.log(`📍 Started at: http://localhost:3000/auth/login`);
    console.log(`📍 Ended at: ${page.url()}`);
    console.log(`📊 Generated 5 debug screenshots`);
    console.log(`🍪 Found ${cookies.length} cookies`);
    console.log(`💾 Found ${Object.keys(localStorage).length} localStorage items`);
    
    if (page.url().includes('login')) {
      console.log('\n❌ ISSUE: Still on login page after authentication attempt');
      console.log('💡 Possible causes:');
      console.log('   - Form validation errors');
      console.log('   - Network/API issues'); 
      console.log('   - Frontend JavaScript errors');
      console.log('   - Backend authentication problems');
      console.log('\n🔍 Check the debug screenshots and network logs above for clues');
    } else {
      console.log('\n✅ SUCCESS: Moved away from login page');
    }
    
  } catch (error) {
    console.error('❌ Debug error:', error.message);
    await page.screenshot({ path: 'debug-error.png', fullPage: true });
  } finally {
    await browser.close();
    console.log('\n🏁 Debug analysis complete! Check debug-*.png files');
  }
})();