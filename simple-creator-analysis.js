const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 1000
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();
  
  try {
    console.log('🚀 Simple creator analysis - bypassing auth issues...');
    
    // Try multiple approaches to get to the creator page
    const attempts = [
      'http://localhost:3000/analytics/latifalshamsi',
      'http://localhost:3000/creators',
      'http://localhost:3000/dashboard',
      'http://localhost:3000'
    ];
    
    let successUrl = null;
    
    for (const url of attempts) {
      try {
        console.log(`🔍 Trying: ${url}`);
        await page.goto(url, { waitUntil: 'networkidle', timeout: 10000 });
        await page.waitForTimeout(3000);
        
        const currentUrl = page.url();
        console.log(`📍 Landed on: ${currentUrl}`);
        
        // If we're not on a login page, we found a good starting point
        if (!currentUrl.includes('/auth/login')) {
          successUrl = currentUrl;
          console.log(`✅ Success! Found accessible page: ${successUrl}`);
          break;
        }
        
        // If we're on login, try to authenticate quickly
        if (currentUrl.includes('/auth/login')) {
          console.log('🔐 Quick auth attempt...');
          
          try {
            await page.fill('input[name="email"]', 'client@analyticsfollowing.com', { timeout: 5000 });
            await page.fill('input[name="password"]', 'ClientPass2024!', { timeout: 5000 });
            await page.click('button[type="submit"]', { timeout: 5000 });
            await page.waitForTimeout(5000);
            
            const postAuthUrl = page.url();
            if (!postAuthUrl.includes('/auth/login')) {
              successUrl = postAuthUrl;
              console.log(`✅ Auth successful! Now at: ${successUrl}`);
              break;
            }
          } catch (authError) {
            console.log(`❌ Auth failed: ${authError.message}`);
          }
        }
        
      } catch (error) {
        console.log(`❌ Failed to access ${url}: ${error.message}`);
      }
    }
    
    if (!successUrl) {
      console.log('❌ Could not access any page. Taking screenshot of current state...');
      await page.screenshot({ path: 'access-failed.png', fullPage: true });
      return;
    }
    
    // Now analyze whatever page we successfully reached
    console.log('\\n🔍 === ANALYZING ACCESSIBLE PAGE ===\\n');
    
    await page.screenshot({ path: 'accessible-page.png', fullPage: true });
    
    const pageTitle = await page.title();
    console.log(`📄 Page Title: "${pageTitle}"`);
    console.log(`📍 Current URL: ${page.url()}`);
    
    // Get all text content to understand the page
    const bodyText = await page.textContent('body');
    console.log(`\\n📄 Page Content Preview (first 500 chars):`);
    console.log(bodyText.slice(0, 500) + '...');
    
    // Look for any creator/profile related links or content
    console.log('\\n🔍 === LOOKING FOR CREATOR/PROFILE CONTENT ===');
    
    const creatorSelectors = [
      'a[href*="analytics"], a[href*="profile"], a[href*="creator"]',
      'button:has-text("latifalshamsi" i), a:has-text("latifalshamsi" i)',
      '.profile, .creator, .user',
      'input[placeholder*="search" i], input[type="search"]'
    ];
    
    for (const selector of creatorSelectors) {
      try {
        const elements = await page.locator(selector).all();
        if (elements.length > 0) {
          console.log(`✅ Found ${elements.length} elements with: ${selector}`);
          
          // Try to interact with the first few
          for (let i = 0; i < Math.min(3, elements.length); i++) {
            const element = elements[i];
            const text = await element.textContent().catch(() => '');
            const href = await element.getAttribute('href').catch(() => null);
            
            console.log(`   ${i + 1}. "${text.trim()}" ${href ? `(${href})` : ''}`);
            
            // If this looks like a way to get to latifalshamsi, try clicking it
            if (text.toLowerCase().includes('latifalshamsi') || 
                href && href.includes('latifalshamsi')) {
              try {
                console.log(`🎯 Clicking element that might lead to latifalshamsi...`);
                await element.click();
                await page.waitForTimeout(5000);
                
                const newUrl = page.url();
                console.log(`📍 After click: ${newUrl}`);
                
                if (newUrl.includes('latifalshamsi') || newUrl.includes('analytics')) {
                  console.log(`🎉 Successfully navigated to creator page!`);
                  break;
                }
              } catch (clickError) {
                console.log(`❌ Click failed: ${clickError.message}`);
              }
            }
          }
        }
      } catch (e) {
        // Continue to next selector
      }
    }
    
    // Try search functionality if available
    try {
      const searchInput = page.locator('input[type="search"], input[placeholder*="search" i]').first();
      if (await searchInput.isVisible({ timeout: 3000 }).catch(() => false)) {
        console.log('🔍 Found search input - searching for latifalshamsi...');
        await searchInput.fill('latifalshamsi');
        await page.keyboard.press('Enter');
        await page.waitForTimeout(5000);
        
        console.log(`📍 After search: ${page.url()}`);
        await page.screenshot({ path: 'after-search.png', fullPage: true });
      }
    } catch (searchError) {
      console.log(`❌ Search failed: ${searchError.message}`);
    }
    
    // Final analysis of whatever page we're on
    console.log('\\n🔍 === FINAL PAGE ANALYSIS ===');
    
    await page.screenshot({ path: 'final-analysis.png', fullPage: true });
    
    // Look for any data visualization elements
    const dataElements = [
      'table, .table',
      'canvas, svg',
      '.chart, .graph',
      '.metric, .stat, .kpi',
      '.card, .widget',
      'h1, h2, h3, h4, h5, h6'
    ];
    
    for (const selector of dataElements) {
      try {
        const elements = await page.locator(selector).all();
        if (elements.length > 0) {
          console.log(`📊 Found ${elements.length} ${selector} elements`);
          
          // Show content of first few elements
          for (let i = 0; i < Math.min(3, elements.length); i++) {
            const text = await elements[i].textContent().catch(() => '');
            if (text.trim() && text.length < 100) {
              console.log(`   - "${text.trim()}"`);
            }
          }
        }
      } catch (e) {
        // Continue
      }
    }
    
    console.log('\\n✅ === ANALYSIS COMPLETE ===');
    console.log('📸 Check the generated PNG files for visual details');
    console.log('📝 This analysis shows what was accessible without full authentication');
    
  } catch (error) {
    console.error('❌ Error:', error);
    await page.screenshot({ path: 'error.png', fullPage: true });
  } finally {
    await browser.close();
  }
})();