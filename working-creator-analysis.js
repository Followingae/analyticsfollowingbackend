const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 2000  // Slow down to see what's happening
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();
  
  try {
    console.log('🚀 WORKING CREATOR ANALYSIS - No waiting for navigation\n');
    
    // Step 1: Simple login without waiting for navigation
    console.log('🔐 Step 1: Login...');
    await page.goto('http://localhost:3000/auth/login');
    await page.waitForTimeout(3000);
    
    // Fill and submit login form
    await page.fill('input[name="email"]', 'client@analyticsfollowing.com');
    await page.fill('input[name="password"]', 'ClientPass2024!');
    await page.click('button[type="submit"]');
    
    // Wait for response and check URL
    await page.waitForTimeout(5000);
    console.log('📍 After login URL:', page.url());
    
    // Step 2: Navigate directly to creator page
    console.log('\n📍 Step 2: Direct navigation to creator analytics...');
    await page.goto('http://localhost:3000/analytics/latifalshamsi');
    await page.waitForTimeout(5000);
    
    const finalUrl = page.url();
    console.log('📍 Final URL:', finalUrl);
    
    // Check if we successfully reached the creator page
    if (finalUrl.includes('latifalshamsi') || (finalUrl.includes('analytics') && !finalUrl.includes('login'))) {
      console.log('🎉 SUCCESS! Reached creator analytics page!\n');
      
      // Take full page screenshot
      await page.screenshot({ path: 'creator-page-success.png', fullPage: true });
      
      // === COMPREHENSIVE ANALYSIS STARTS HERE ===
      console.log('🔍 === COMPREHENSIVE CREATOR PAGE ANALYSIS ===\n');
      
      const pageTitle = await page.title();
      console.log('📄 Page Title:', pageTitle);
      
      // Get all text content for overview
      const bodyText = await page.textContent('body');
      console.log('📄 Page contains latifalshamsi:', bodyText.toLowerCase().includes('latifalshamsi'));
      
      // === PROFILE HEADER FIELDS ===
      console.log('\n👤 === PROFILE HEADER FIELDS ===');
      
      const headerFields = {
        'Profile Image': 'img[alt*="profile" i], .avatar img, img[src*="profile"], img[src*="instagram"]',
        'Username': 'h1, h2, .username, .handle, [data-testid*="username"]',
        'Display Name': '.full-name, .display-name, .name, h3',
        'Followers Count': '.followers, .follower-count, [data-testid*="followers"]',
        'Following Count': '.following, .following-count, [data-testid*="following"]',
        'Posts Count': '.posts, .post-count, [data-testid*="posts"]',
        'Engagement Rate': '.engagement, .engagement-rate, .rate',
        'Verification Badge': '.verified, .verification, .badge',
        'Bio/Description': '.bio, .description, .about'
      };
      
      for (const [fieldName, selector] of Object.entries(headerFields)) {
        try {
          const element = page.locator(selector).first();
          const isVisible = await element.isVisible({ timeout: 2000 }).catch(() => false);
          
          if (isVisible) {
            const text = await element.textContent().catch(() => '');
            const src = await element.getAttribute('src').catch(() => '');
            const value = text.trim() || src || 'Present';
            
            console.log(`✅ ${fieldName}: "${value}"`);
          } else {
            console.log(`❌ ${fieldName}: Not found`);
          }
        } catch (e) {
          console.log(`❌ ${fieldName}: Error`);
        }
      }
      
      // === NAVIGATION TABS ===
      console.log('\n📑 === NAVIGATION TABS ===');
      
      const tabElements = await page.locator('nav a, .nav-link, [role="tab"], .tab, button[role="tab"]').all();
      console.log(`Found ${tabElements.length} potential tab elements`);
      
      const tabs = [];
      for (let i = 0; i < tabElements.length; i++) {
        try {
          const element = tabElements[i];
          const isVisible = await element.isVisible().catch(() => false);
          
          if (isVisible) {
            const text = await element.textContent().catch(() => '');
            const href = await element.getAttribute('href').catch(() => null);
            
            if (text.trim() && text.length < 30) {
              tabs.push({
                text: text.trim(),
                href: href,
                element: element
              });
            }
          }
        } catch (e) {
          // Continue
        }
      }
      
      // Remove duplicates
      const uniqueTabs = tabs.filter((tab, index, self) => 
        index === self.findIndex(t => t.text === tab.text)
      );
      
      console.log(`📑 Found ${uniqueTabs.length} unique tabs:`);
      uniqueTabs.forEach((tab, i) => {
        console.log(`  ${i + 1}. "${tab.text}" ${tab.href ? `(${tab.href})` : ''}`);
      });
      
      // === CLICK THROUGH TABS AND ANALYZE ===
      console.log('\n🔄 === TAB CONTENT ANALYSIS ===');
      
      for (let i = 0; i < Math.min(4, uniqueTabs.length); i++) {
        const tab = uniqueTabs[i];
        
        try {
          console.log(`\n🎯 Clicking tab: "${tab.text}"`);
          
          await tab.element.click();
          await page.waitForTimeout(3000);
          
          // Take screenshot
          const filename = `tab-${i + 1}-${tab.text.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase()}.png`;
          await page.screenshot({ path: filename, fullPage: true });
          console.log(`📸 Screenshot: ${filename}`);
          
          // Quick content analysis
          const analysis = {
            metrics: 0,
            charts: 0,
            tables: 0,
            aiElements: 0,
            errors: 0
          };
          
          // Count different types of content
          analysis.metrics = await page.locator('.metric, .stat, .kpi, .number, .count, .percentage').count();
          analysis.charts = await page.locator('canvas, svg, .chart, .graph').count();
          analysis.tables = await page.locator('table, .table').count();
          analysis.aiElements = await page.locator('[data-testid*="ai"], [class*="ai"], .sentiment, .category').count();
          analysis.errors = await page.locator('.error, .alert-error, [role="alert"], .loading, .spinner').count();
          
          console.log(`📊 Content summary:`);
          console.log(`   📈 Metrics: ${analysis.metrics}`);
          console.log(`   📊 Charts: ${analysis.charts}`);
          console.log(`   📋 Tables: ${analysis.tables}`);
          console.log(`   🤖 AI Elements: ${analysis.aiElements}`);
          console.log(`   ⚠️ Errors/Loading: ${analysis.errors}`);
          
          // Get some sample text content
          const contentText = await page.locator('main, .main-content, .content').first().textContent().catch(() => '');
          if (contentText.trim()) {
            console.log(`   📄 Content preview: "${contentText.slice(0, 200).trim()}..."`);
          }
          
        } catch (tabError) {
          console.log(`❌ Error with tab "${tab.text}": ${tabError.message}`);
        }
      }
      
      // === SPECIFIC DATA ANALYSIS ===
      console.log('\n📊 === SPECIFIC DATA ELEMENTS ===');
      
      // Look for specific metrics
      const specificElements = {
        'Engagement Rate Values': '.engagement-rate, .rate, [data-testid*="engagement"]',
        'Follower Numbers': '.followers, .follower-count, [data-testid*="followers"]',
        'AI Sentiment Data': '.sentiment, .sentiment-score, [data-testid*="sentiment"]',
        'Content Categories': '.category, .content-category, [data-testid*="category"]',
        'Charts/Graphs': 'canvas, svg',
        'Data Tables': 'table tbody tr',
        'Loading States': '.loading, .spinner, .skeleton, .analyzing',
        'Error Messages': '.error, .alert-error, [role="alert"]'
      };
      
      for (const [elementType, selector] of Object.entries(specificElements)) {
        try {
          const elements = await page.locator(selector).all();
          console.log(`${elementType}: ${elements.length} found`);
          
          // Show first few values if they exist
          for (let i = 0; i < Math.min(3, elements.length); i++) {
            const text = await elements[i].textContent().catch(() => '');
            if (text.trim() && text.length < 100) {
              console.log(`   - "${text.trim()}"`);
            }
          }
        } catch (e) {
          console.log(`${elementType}: Error checking`);
        }
      }
      
      // === FINAL SCREENSHOT ===
      await page.screenshot({ path: 'final-comprehensive-analysis.png', fullPage: true });
      
      console.log('\n🎯 === ANALYSIS COMPLETE ===');
      console.log('✅ Successfully analyzed creator page with authentication');
      console.log('📸 Generated multiple screenshots showing all tabs and content');
      console.log('📊 Documented all visible fields, metrics, and interactive elements');
      
    } else {
      console.log('❌ Did not reach creator page. Current URL:', finalUrl);
      
      if (finalUrl.includes('login')) {
        console.log('⚠️ Still on login page - authentication may have failed');
        
        // Check for error messages
        const alerts = await page.locator('[role="alert"]').all();
        for (const alert of alerts) {
          const text = await alert.textContent().catch(() => '');
          if (text.trim()) {
            console.log(`⚠️ Alert: "${text.trim()}"`);
          }
        }
      }
      
      await page.screenshot({ path: 'failed-to-reach-creator-page.png', fullPage: true });
    }
    
  } catch (error) {
    console.error('❌ Error:', error.message);
    await page.screenshot({ path: 'error-screenshot.png', fullPage: true });
  } finally {
    await browser.close();
    console.log('\n🏁 Browser closed. Check PNG files for visual analysis!');
  }
})();