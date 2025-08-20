const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 1000 // Slow down for observation
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  
  const page = await context.newPage();
  
  try {
    console.log('🚀 Starting comprehensive creator page analysis...');
    
    // Navigate to the frontend (assuming it runs on localhost:3000)
    console.log('📍 Navigating to frontend...');
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
    
    // Wait for page to load
    await page.waitForTimeout(3000);
    
    console.log('📋 Current page title:', await page.title());
    console.log('📋 Current URL:', page.url());
    
    // Take a screenshot of the homepage
    await page.screenshot({ path: 'homepage.png', fullPage: true });
    console.log('📸 Homepage screenshot saved as homepage.png');
    
    // Look for navigation or search to get to a creator page
    // First, let's see what elements are available
    const bodyText = await page.textContent('body');
    console.log('📄 Page content preview (first 500 chars):', bodyText.slice(0, 500));
    
    // Try to find login/auth elements if needed
    const loginButton = page.locator('button:has-text("Login"), button:has-text("Sign in"), a:has-text("Login"), a:has-text("Sign in")').first();
    
    // Handle authentication if login page is detected
    if (page.url().includes('/auth/login') || await loginButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      console.log('🔐 Login required - filling credentials...');
      
      // Take screenshot of auth page first
      await page.screenshot({ path: 'auth-page.png', fullPage: true });
      console.log('📸 Auth page screenshot saved as auth-page.png');
      
      // Look for email/username input
      const emailInput = page.locator('input[type="email"], input[name="email"], input[placeholder*="email"], input[placeholder*="Email"]').first();
      const passwordInput = page.locator('input[type="password"], input[name="password"], input[placeholder*="password"], input[placeholder*="Password"]').first();
      
      if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
        console.log('📧 Filling email...');
        await emailInput.fill('client@analyticsfollowing.com');
        await page.waitForTimeout(1000);
      }
      
      if (await passwordInput.isVisible({ timeout: 5000 }).catch(() => false)) {
        console.log('🔑 Filling password...');
        await passwordInput.fill('ClientPass2024!');
        await page.waitForTimeout(1000);
      }
      
      // Look for login/submit button
      const submitButton = page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign in"), input[type="submit"]').first();
      
      if (await submitButton.isVisible({ timeout: 5000 }).catch(() => false)) {
        console.log('✅ Clicking login button...');
        await submitButton.click();
        await page.waitForTimeout(5000); // Wait longer for authentication
        
        console.log('🔄 Post-login URL:', page.url());
        
        // Take screenshot after login
        await page.screenshot({ path: 'post-login.png', fullPage: true });
        console.log('📸 Post-login screenshot saved');
      } else {
        console.log('❌ Could not find login button');
      }
    }
    
    // Try to navigate to a creator page or search
    // Look for search functionality
    const searchInput = page.locator('input[type="search"], input[placeholder*="search"], input[placeholder*="Search"], input[name*="search"]').first();
    
    if (await searchInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      console.log('🔍 Found search input - searching for latifalshamsi...');
      await searchInput.fill('latifalshamsi');
      await page.keyboard.press('Enter');
      await page.waitForTimeout(3000);
      
      // Look for creator results or direct navigation
      const creatorLink = page.locator('a:has-text("latifalshamsi"), button:has-text("latifalshamsi")').first();
      
      if (await creatorLink.isVisible({ timeout: 5000 }).catch(() => false)) {
        console.log('👤 Found creator link - clicking...');
        await creatorLink.click();
        await page.waitForTimeout(3000);
      }
    } else {
      // Try direct navigation to creator page if URL pattern is known
      console.log('🎯 Trying direct navigation to creator page...');
      await page.goto('http://localhost:3000/analytics/latifalshamsi', { waitUntil: 'networkidle' });
      await page.waitForTimeout(3000);
    }
    
    console.log('📍 Current URL after navigation:', page.url());
    
    // Take screenshot of the creator page
    await page.screenshot({ path: 'creator-page-full.png', fullPage: true });
    console.log('📸 Creator page screenshot saved as creator-page-full.png');
    
    // Now analyze all elements, fields, and tabs on the creator page
    console.log('\\n🔍 === COMPREHENSIVE CREATOR PAGE ANALYSIS ===\\n');
    
    // 1. Page title and basic info
    const pageTitle = await page.title();
    console.log('📄 Page Title:', pageTitle);
    
    // 2. Look for main profile information
    console.log('\\n👤 === PROFILE INFORMATION SECTION ===');
    
    const profileElements = {
      username: 'h1, h2, .username, [data-testid*="username"]',
      fullName: '.full-name, .display-name, h2, h3',
      followerCount: '.followers, [data-testid*="followers"], .follower-count',
      followingCount: '.following, [data-testid*="following"], .following-count',
      postsCount: '.posts, [data-testid*="posts"], .post-count',
      bio: '.bio, .description, .profile-description',
      profileImage: 'img[alt*="profile"], .profile-image img, .avatar img'
    };
    
    for (const [field, selector] of Object.entries(profileElements)) {
      try {
        const element = page.locator(selector).first();
        const isVisible = await element.isVisible({ timeout: 2000 }).catch(() => false);
        
        if (isVisible) {
          const text = await element.textContent().catch(() => '');
          const src = await element.getAttribute('src').catch(() => null);
          console.log(`✅ ${field.toUpperCase()}:`, text || src || 'Present');
        } else {
          console.log(`❌ ${field.toUpperCase()}: Not found`);
        }
      } catch (e) {
        console.log(`❌ ${field.toUpperCase()}: Error -`, e.message);
      }
    }
    
    // 3. Look for tabs/navigation sections
    console.log('\\n📑 === TABS AND NAVIGATION ===');
    
    const tabSelectors = [
      'nav a, .nav-link, .tab, [role="tab"]',
      'button[role="tab"], .tab-button',
      '.navigation a, .menu a'
    ];
    
    let foundTabs = [];
    
    for (const selector of tabSelectors) {
      try {
        const tabs = await page.locator(selector).all();
        for (let i = 0; i < tabs.length; i++) {
          const tab = tabs[i];
          const isVisible = await tab.isVisible().catch(() => false);
          if (isVisible) {
            const text = await tab.textContent().catch(() => '');
            const href = await tab.getAttribute('href').catch(() => null);
            if (text.trim()) {
              foundTabs.push({ text: text.trim(), href, index: i });
            }
          }
        }
      } catch (e) {
        // Continue to next selector
      }
    }
    
    foundTabs.forEach((tab, i) => {
      console.log(`📑 Tab ${i + 1}: "${tab.text}" ${tab.href ? `(${tab.href})` : ''}`);
    });
    
    // 4. Click through each tab and analyze content
    console.log('\\n🔄 === ANALYZING TAB CONTENT ===');
    
    for (let i = 0; i < Math.min(foundTabs.length, 5); i++) { // Limit to first 5 tabs
      const tab = foundTabs[i];
      
      try {
        console.log(`\\n🎯 Clicking tab: "${tab.text}"`);
        
        // Find and click the tab
        const tabElement = page.locator(`nav a, .nav-link, .tab, [role="tab"], button[role="tab"], .tab-button`).nth(tab.index);
        await tabElement.click();
        await page.waitForTimeout(2000);
        
        // Take screenshot of this tab
        await page.screenshot({ path: `creator-page-tab-${i + 1}-${tab.text.replace(/[^a-zA-Z0-9]/g, '_')}.png` });
        console.log(`📸 Tab screenshot saved`);
        
        // Analyze content in this tab
        const tabContent = await page.textContent('main, .main-content, .tab-content, .content').catch(() => '');
        console.log(`📄 Tab content preview (first 300 chars):`, tabContent.slice(0, 300));
        
        // Look for specific data fields in this tab
        const dataFields = [
          'table td, table th',
          '.metric, .stat, .data-point',
          '.card .title, .card .value',
          'h3, h4, h5, h6',
          '.engagement, .analytics',
          '.chart, .graph, canvas',
          '.percentage, .score, .rate'
        ];
        
        for (const fieldSelector of dataFields) {
          try {
            const elements = await page.locator(fieldSelector).all();
            if (elements.length > 0) {
              console.log(`  🔍 Found ${elements.length} elements matching: ${fieldSelector}`);
              
              // Show first few elements
              for (let j = 0; j < Math.min(3, elements.length); j++) {
                const text = await elements[j].textContent().catch(() => '');
                if (text.trim()) {
                  console.log(`    - "${text.trim()}"`);
                }
              }
            }
          } catch (e) {
            // Continue to next selector
          }
        }
        
      } catch (e) {
        console.log(`❌ Error analyzing tab "${tab.text}":`, e.message);
      }
    }
    
    // 5. Look for specific AI/Analytics sections
    console.log('\\n🤖 === AI ANALYSIS SECTIONS ===');
    
    const aiSelectors = [
      '.ai-analysis, .ai-insights',
      '.sentiment, .sentiment-analysis',
      '.content-category, .content-type',
      '.language-detection',
      '[data-testid*="ai"], [class*="ai"]',
      '.loading, .spinner, .analyzing'
    ];
    
    for (const selector of aiSelectors) {
      try {
        const elements = await page.locator(selector).all();
        if (elements.length > 0) {
          console.log(`🤖 Found ${elements.length} AI-related elements: ${selector}`);
          for (const element of elements.slice(0, 3)) {
            const text = await element.textContent().catch(() => '');
            if (text.trim()) {
              console.log(`  - "${text.trim()}"`);
            }
          }
        }
      } catch (e) {
        // Continue
      }
    }
    
    // 6. Check for loading states, errors, or incomplete data
    console.log('\\n⚠️ === LOADING STATES AND ERRORS ===');
    
    const stateSelectors = [
      '.loading, .spinner, .skeleton',
      '.error, .warning, .alert',
      '.empty, .no-data, .not-found',
      '.incomplete, .pending'
    ];
    
    for (const selector of stateSelectors) {
      try {
        const elements = await page.locator(selector).all();
        if (elements.length > 0) {
          console.log(`⚠️ Found ${elements.length} state indicators: ${selector}`);
          for (const element of elements.slice(0, 3)) {
            const text = await element.textContent().catch(() => '');
            if (text.trim()) {
              console.log(`  - "${text.trim()}"`);
            }
          }
        }
      } catch (e) {
        // Continue
      }
    }
    
    // 7. Final comprehensive screenshot
    await page.screenshot({ path: 'creator-page-final.png', fullPage: true });
    console.log('\\n📸 Final comprehensive screenshot saved as creator-page-final.png');
    
    console.log('\\n✅ === ANALYSIS COMPLETE ===');
    console.log('📊 Check the generated PNG files for visual analysis');
    console.log('🎯 Analysis focused on latifalshamsi profile page');
    
  } catch (error) {
    console.error('❌ Error during analysis:', error);
    await page.screenshot({ path: 'error-page.png', fullPage: true });
    console.log('📸 Error screenshot saved as error-page.png');
  } finally {
    await browser.close();
    console.log('🏁 Browser closed. Analysis complete!');
  }
})();