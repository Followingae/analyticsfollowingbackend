const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 1000
  });
  
  // Create context with session persistence
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    // Accept all cookies and local storage
    acceptDownloads: true,
    ignoreHTTPSErrors: true
  });
  
  const page = await context.newPage();
  
  try {
    console.log('🔐 === PERSISTENT AUTHENTICATION ANALYSIS ===\n');
    
    // Step 1: Login and wait for proper authentication
    console.log('Step 1: Logging in with session persistence...');
    await page.goto('http://localhost:3000/auth/login', { waitUntil: 'networkidle' });
    
    // Wait for page to fully load
    await page.waitForTimeout(3000);
    
    // Fill credentials
    await page.fill('input[name="email"]', 'client@analyticsfollowing.com');
    await page.fill('input[name="password"]', 'ClientPass2024!');
    
    console.log('🔑 Submitting credentials...');
    
    // Click login and wait for navigation
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'networkidle', timeout: 15000 }),
      page.click('button[type="submit"]')
    ]);
    
    const postLoginUrl = page.url();
    console.log('✅ Post-login URL:', postLoginUrl);
    
    // Wait a bit more to ensure session is established
    await page.waitForTimeout(3000);
    
    // Check if we're authenticated by looking for user-specific content
    const isAuthenticated = !postLoginUrl.includes('/auth/login');
    
    if (isAuthenticated) {
      console.log('🎉 Authentication successful! Session established.');
      
      // Save the authentication state for future use
      await page.screenshot({ path: 'auth-successful-dashboard.png', fullPage: true });
      
      // Step 2: Navigate to creators/analytics with preserved session
      console.log('\nStep 2: Navigating to creator analytics with preserved session...');
      
      // Try different navigation approaches
      const navigationAttempts = [
        'http://localhost:3000/analytics/latifalshamsi',
        'http://localhost:3000/creators'
      ];
      
      let analyticsReached = false;
      
      for (const url of navigationAttempts) {
        try {
          console.log(`🎯 Attempting navigation to: ${url}`);
          
          await page.goto(url, { waitUntil: 'networkidle', timeout: 10000 });
          await page.waitForTimeout(3000);
          
          const currentUrl = page.url();
          console.log(`📍 Landed on: ${currentUrl}`);
          
          // Check if we stayed authenticated (not redirected to login)
          if (!currentUrl.includes('/auth/login')) {
            console.log('✅ Navigation successful with preserved session!');
            analyticsReached = true;
            
            await page.screenshot({ path: `navigation-success-${url.split('/').pop()}.png`, fullPage: true });
            
            // If this is a creators list page, look for latifalshamsi
            if (currentUrl.includes('/creators')) {
              console.log('🔍 Looking for latifalshamsi in creators list...');
              
              // Wait for page content to load
              await page.waitForTimeout(2000);
              
              // Look for latifalshamsi link/button
              const latifaSelectors = [
                'a:has-text("latifalshamsi" i)',
                'button:has-text("latifalshamsi" i)',
                '[href*="latifalshamsi"]',
                '.creator-card:has-text("latifalshamsi" i)',
                '.profile:has-text("latifalshamsi" i)'
              ];
              
              let foundLatifa = false;
              
              for (const selector of latifaSelectors) {
                try {
                  const latifaElement = page.locator(selector).first();
                  
                  if (await latifaElement.isVisible({ timeout: 3000 }).catch(() => false)) {
                    console.log(`✅ Found latifalshamsi with selector: ${selector}`);
                    
                    await latifaElement.click();
                    await page.waitForTimeout(3000);
                    
                    const profileUrl = page.url();
                    console.log(`📍 Profile URL: ${profileUrl}`);
                    
                    if (profileUrl.includes('latifalshamsi') || profileUrl.includes('analytics')) {
                      foundLatifa = true;
                      break;
                    }
                  }
                } catch (e) {
                  // Continue to next selector
                }
              }
              
              if (!foundLatifa) {
                // Try search if available
                try {
                  const searchInput = page.locator('input[type="search"], input[placeholder*="search" i]').first();
                  
                  if (await searchInput.isVisible({ timeout: 3000 }).catch(() => false)) {
                    console.log('🔍 Using search to find latifalshamsi...');
                    await searchInput.fill('latifalshamsi');
                    await page.keyboard.press('Enter');
                    await page.waitForTimeout(3000);
                    
                    // Click on search result
                    const searchResult = page.locator('a:has-text("latifalshamsi" i), button:has-text("latifalshamsi" i)').first();
                    if (await searchResult.isVisible({ timeout: 3000 }).catch(() => false)) {
                      await searchResult.click();
                      await page.waitForTimeout(3000);
                      foundLatifa = true;
                    }
                  }
                } catch (searchError) {
                  console.log('❌ Search failed:', searchError.message);
                }
              }
              
              if (!foundLatifa) {
                console.log('⚠️ Could not find latifalshamsi in creators list, trying direct navigation...');
                await page.goto('http://localhost:3000/analytics/latifalshamsi', { waitUntil: 'networkidle' });
                await page.waitForTimeout(3000);
              }
            }
            
            break; // Success, no need to try other URLs
          } else {
            console.log('❌ Redirected to login - session lost');
          }
          
        } catch (navError) {
          console.log(`❌ Navigation failed: ${navError.message}`);
        }
      }
      
      if (analyticsReached) {
        // Step 3: Comprehensive analysis of the reached page
        console.log('\n🎯 Step 3: COMPREHENSIVE CREATOR PAGE ANALYSIS');
        
        const finalUrl = page.url();
        console.log(`📍 Analyzing page: ${finalUrl}`);
        
        await page.screenshot({ path: 'creator-analysis-page.png', fullPage: true });
        
        // === PAGE TITLE AND BASIC INFO ===
        const pageTitle = await page.title();
        console.log(`📄 Page Title: "${pageTitle}"`);
        
        // === PROFILE INFORMATION SECTION ===
        console.log('\n👤 === PROFILE HEADER ANALYSIS ===');
        
        const profileFields = [
          { name: 'Profile Image', selector: 'img[alt*="profile" i], .avatar img, img[src*="profile"]' },
          { name: 'Username/Handle', selector: 'h1, h2, .username, .handle' },
          { name: 'Full Name', selector: '.full-name, .display-name, .name' },
          { name: 'Followers', selector: '.followers, .follower-count, [data-testid*="followers"]' },
          { name: 'Following', selector: '.following, .following-count, [data-testid*="following"]' },
          { name: 'Posts Count', selector: '.posts, .post-count, [data-testid*="posts"]' },
          { name: 'Engagement Rate', selector: '.engagement, .engagement-rate' },
          { name: 'Bio/Description', selector: '.bio, .description, .about' }
        ];
        
        const foundFields = [];
        
        for (const field of profileFields) {
          try {
            const elements = await page.locator(field.selector).all();
            let found = false;
            
            for (const element of elements) {
              const isVisible = await element.isVisible().catch(() => false);
              if (isVisible) {
                const text = await element.textContent().catch(() => '');
                const src = await element.getAttribute('src').catch(() => null);
                
                if (text.trim() || src) {
                  foundFields.push({
                    field: field.name,
                    value: text.trim() || src,
                    selector: field.selector
                  });
                  console.log(`✅ ${field.name}: "${text.trim() || src}" [${field.selector}]`);
                  found = true;
                  break;
                }
              }
            }
            
            if (!found) {
              console.log(`❌ ${field.name}: Not found`);
            }
          } catch (e) {
            console.log(`❌ ${field.name}: Error - ${e.message}`);
          }
        }
        
        // === NAVIGATION TABS ===
        console.log('\n📑 === NAVIGATION TABS ANALYSIS ===');
        
        const tabSelectors = [
          'nav a, .nav-link',
          '[role="tab"], .tab',
          'button[role="tab"]',
          '.navigation a',
          'button:has-text("Overview"), button:has-text("Posts"), button:has-text("Analytics"), button:has-text("AI")'
        ];
        
        const foundTabs = [];
        
        for (const selector of tabSelectors) {
          try {
            const elements = await page.locator(selector).all();
            
            for (const element of elements) {
              const isVisible = await element.isVisible().catch(() => false);
              if (isVisible) {
                const text = await element.textContent().catch(() => '');
                const href = await element.getAttribute('href').catch(() => null);
                
                if (text.trim() && text.length > 1 && text.length < 50) {
                  foundTabs.push({
                    text: text.trim(),
                    href: href,
                    element: element,
                    selector: selector
                  });
                }
              }
            }
          } catch (e) {
            // Continue
          }
        }
        
        // Remove duplicates
        const uniqueTabs = foundTabs.filter((tab, index, self) => 
          index === self.findIndex(t => t.text.toLowerCase() === tab.text.toLowerCase())
        );
        
        console.log(`📑 Found ${uniqueTabs.length} navigation tabs:`);
        uniqueTabs.forEach((tab, i) => {
          console.log(`  ${i + 1}. "${tab.text}" ${tab.href ? `(${tab.href})` : ''}`);
        });
        
        // === CLICK THROUGH TABS AND ANALYZE CONTENT ===
        console.log('\n🔄 === TAB CONTENT DETAILED ANALYSIS ===');
        
        for (let i = 0; i < Math.min(5, uniqueTabs.length); i++) {
          const tab = uniqueTabs[i];
          
          try {
            console.log(`\n🎯 Analyzing Tab ${i + 1}: "${tab.text}"`);
            
            // Click the tab
            await tab.element.click();
            await page.waitForTimeout(4000);
            
            // Take screenshot
            const filename = `tab-${i + 1}-${tab.text.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase()}.png`;
            await page.screenshot({ path: filename, fullPage: true });
            console.log(`📸 Screenshot saved: ${filename}`);
            
            // Analyze content
            console.log('📊 Content Analysis:');
            
            // Metrics
            const metrics = await page.locator('.metric, .stat, .kpi, .number, .count, .percentage').all();
            console.log(`   📈 Metrics found: ${metrics.length}`);
            for (let j = 0; j < Math.min(5, metrics.length); j++) {
              const text = await metrics[j].textContent().catch(() => '');
              if (text.trim()) {
                console.log(`      - "${text.trim()}"`);
              }
            }
            
            // Charts/Visualizations
            const charts = await page.locator('canvas, svg, .chart, .graph').all();
            console.log(`   📊 Charts/Visualizations: ${charts.length}`);
            
            // Tables
            const tables = await page.locator('table, .table').all();
            console.log(`   📋 Tables: ${tables.length}`);
            
            if (tables.length > 0) {
              try {
                const firstTable = tables[0];
                const headers = await firstTable.locator('th').all();
                const headerTexts = [];
                
                for (const header of headers.slice(0, 6)) {
                  const text = await header.textContent().catch(() => '');
                  if (text.trim()) headerTexts.push(text.trim());
                }
                
                if (headerTexts.length > 0) {
                  console.log(`      - Headers: ${headerTexts.join(', ')}`);
                }
              } catch (e) {
                console.log('      - Table found but could not parse headers');
              }
            }
            
            // AI Elements
            const aiElements = await page.locator('[data-testid*="ai"], [class*="ai"], .sentiment, .category').all();
            console.log(`   🤖 AI Elements: ${aiElements.length}`);
            for (let j = 0; j < Math.min(3, aiElements.length); j++) {
              const text = await aiElements[j].textContent().catch(() => '');
              if (text.trim() && text.length < 100) {
                console.log(`      - "${text.trim()}"`);
              }
            }
            
            // Loading states
            const loadingElements = await page.locator('.loading, .spinner, .skeleton, .animate-pulse').all();
            if (loadingElements.length > 0) {
              console.log(`   ⏳ Loading states: ${loadingElements.length}`);
            }
            
            // Errors
            const errorElements = await page.locator('.error, .alert-error, [role="alert"]').all();
            if (errorElements.length > 0) {
              console.log(`   ⚠️ Errors/Alerts: ${errorElements.length}`);
              for (let j = 0; j < Math.min(2, errorElements.length); j++) {
                const text = await errorElements[j].textContent().catch(() => '');
                if (text.trim()) {
                  console.log(`      - "${text.trim()}"`);
                }
              }
            }
            
          } catch (tabError) {
            console.log(`❌ Error analyzing tab "${tab.text}": ${tabError.message}`);
          }
        }
        
        // === FINAL SUMMARY ===
        console.log('\n🎯 === COMPREHENSIVE ANALYSIS SUMMARY ===');
        console.log(`✅ Successfully analyzed creator page: ${finalUrl}`);
        console.log(`📋 Profile fields found: ${foundFields.length}`);
        console.log(`📑 Navigation tabs analyzed: ${Math.min(5, uniqueTabs.length)}`);
        console.log(`📸 Screenshots generated: ${Math.min(5, uniqueTabs.length) + 3}`);
        
        console.log('\n📊 Field Implementation Status:');
        foundFields.forEach(field => {
          console.log(`   ✅ ${field.field} - Handled via ${field.selector}`);
        });
        
        console.log('\n🎯 This analysis shows exactly how your creator page fields are implemented!');
        
      } else {
        console.log('❌ Could not reach analytics page even with preserved session');
      }
      
    } else {
      console.log('❌ Authentication failed - still on login page');
      await page.screenshot({ path: 'auth-failed.png', fullPage: true });
      
      // Check for error messages
      const errorElements = await page.locator('[role="alert"], .error, .alert-error').all();
      if (errorElements.length > 0) {
        console.log('⚠️ Error messages found:');
        for (const error of errorElements) {
          const text = await error.textContent().catch(() => '');
          if (text.trim()) {
            console.log(`   - ${text.trim()}`);
          }
        }
      }
    }
    
    // Final screenshot
    await page.screenshot({ path: 'final-comprehensive-analysis.png', fullPage: true });
    
  } catch (error) {
    console.error('❌ Critical error:', error);
    await page.screenshot({ path: 'critical-error-final.png', fullPage: true });
  } finally {
    await browser.close();
    console.log('\n✅ Analysis complete! Check all generated PNG files for visual reference.');
  }
})();