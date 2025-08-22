const { chromium } = require('playwright');

async function verifyFixes() {
  console.log('🔧 Verifying Backend Fixes...');
  console.log('===============================');
  
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 1000
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();
  
  const apiCalls = [];
  const errors = [];
  
  page.on('response', response => {
    if (response.url().includes('/api/')) {
      apiCalls.push({
        url: response.url(),
        status: response.status(),
        method: response.request().method()
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

  try {
    // Login first
    await page.goto('http://localhost:3000/login');
    await page.waitForSelector('input[type="email"]');
    await page.fill('input[type="email"]', 'client@analyticsfollowing.com');
    await page.fill('input[type="password"]', 'ClientPass2024!');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);
    console.log('✅ Login completed');

    // Test Dashboard (Credits API)
    console.log('\n🧪 Testing Dashboard (Credits API fixes)...');
    const beforeCredits = errors.length;
    await page.goto('http://localhost:3000/dashboard');
    await page.waitForTimeout(5000);
    
    const creditsErrors = errors.slice(beforeCredits);
    const creditsCalls = apiCalls.filter(call => call.url.includes('credits')).slice(-10);
    
    console.log(`📡 Credits API calls made: ${creditsCalls.length}`);
    creditsCalls.forEach(call => {
      const status = call.status < 400 ? '✅' : '❌';
      console.log(`  ${status} ${call.method} ${call.url.replace('http://localhost:8000', '')} (${call.status})`);
    });

    // Test Campaigns Page
    console.log('\n🧪 Testing Campaigns (New API routes)...');
    const beforeCampaigns = errors.length;
    await page.goto('http://localhost:3000/campaigns');
    await page.waitForTimeout(5000);
    
    const campaignsErrors = errors.slice(beforeCampaigns);
    const campaignsCalls = apiCalls.filter(call => call.url.includes('campaigns')).slice(-10);
    
    console.log(`📡 Campaigns API calls made: ${campaignsCalls.length}`);
    campaignsCalls.forEach(call => {
      const status = call.status < 400 ? '✅' : '❌';
      console.log(`  ${status} ${call.method} ${call.url.replace('http://localhost:8000', '')} (${call.status})`);
    });

    // Test Lists Page
    console.log('\n🧪 Testing Lists (Fixed getListTemplates method)...');
    const beforeLists = errors.length;
    await page.goto('http://localhost:3000/my-lists');
    await page.waitForTimeout(5000);
    
    const listsErrors = errors.slice(beforeLists);
    
    // Check for JavaScript errors specifically
    let jsErrors = 0;
    page.on('console', msg => {
      if (msg.type() === 'error' && msg.text().includes('getListTemplates')) {
        jsErrors++;
        console.log(`❌ JS Error: ${msg.text()}`);
      }
    });
    
    await page.waitForTimeout(2000);
    
    if (jsErrors === 0) {
      console.log('✅ No JavaScript errors for getListTemplates method');
    } else {
      console.log(`❌ Found ${jsErrors} JavaScript errors`);
    }

    // Summary
    console.log('\n📊 VERIFICATION RESULTS');
    console.log('=======================');
    console.log(`📡 Total API calls: ${apiCalls.length}`);
    console.log(`❌ Total errors: ${errors.length}`);
    
    const fixedIssues = {
      credits: creditsErrors.length === 0,
      campaigns: campaignsErrors.length === 0,
      lists: jsErrors === 0
    };
    
    console.log('\n🔧 FIXES STATUS:');
    console.log(`Credits API: ${fixedIssues.credits ? '✅ FIXED' : '❌ STILL BROKEN'}`);
    console.log(`Campaigns API: ${fixedIssues.campaigns ? '✅ FIXED' : '❌ STILL BROKEN'}`);
    console.log(`Lists JavaScript: ${fixedIssues.lists ? '✅ FIXED' : '❌ STILL BROKEN'}`);
    
    const totalFixed = Object.values(fixedIssues).filter(Boolean).length;
    console.log(`\n🎯 OVERALL: ${totalFixed}/3 issues fixed`);
    
    if (errors.length > 0) {
      console.log('\n🚨 REMAINING ERRORS:');
      errors.slice(-10).forEach((error, index) => {
        console.log(`${index + 1}. ${error.url} - ${error.status} ${error.statusText}`);
      });
    }

    await page.screenshot({ path: 'verification-complete.png', fullPage: true });
    console.log('📸 Screenshot saved: verification-complete.png');

  } catch (error) {
    console.error('❌ Verification failed:', error.message);
  }

  await browser.close();
}

verifyFixes()
  .then(() => {
    console.log('\n🏁 Verification completed');
  })
  .catch(error => {
    console.error('❌ Verification execution failed:', error);
  });