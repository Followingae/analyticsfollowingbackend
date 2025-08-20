const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 500
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();
  
  // Listen to network requests to debug auth issues
  page.on('response', response => {
    if (response.status() >= 400) {
      console.log(`❌ Network error: ${response.status()} ${response.url()}`);
    }
  });
  
  try {
    console.log('🚀 Starting comprehensive creator analysis with improved login...');
    
    // Go to login page
    await page.goto('http://localhost:3000/auth/login', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    
    console.log('📍 Initial URL:', page.url());
    
    // Take screenshot of login page
    await page.screenshot({ path: 'step1-login-page.png', fullPage: true });
    
    // Fill login form
    console.log('🔐 Filling login form...');
    await page.fill('input[name="email"]', 'client@analyticsfollowing.com');
    await page.fill('input[name="password"]', 'ClientPass2024!');
    
    // Take screenshot of filled form
    await page.screenshot({ path: 'step2-form-filled.png', fullPage: true });
    
    // Click login and wait for navigation
    console.log('✅ Submitting login...');
    const [response] = await Promise.all([
      page.waitForResponse(response => response.url().includes('/auth/') && response.status() === 200, { timeout: 10000 }),
      page.click('button[type="submit"]')
    ]);
    
    console.log('🔄 Login response received:', response.status());
    await page.waitForTimeout(3000);
    
    console.log('📍 Post-login URL:', page.url());
    await page.screenshot({ path: 'step3-post-login.png', fullPage: true });
    
    // If still on login page, try alternative approach
    if (page.url().includes('/auth/login')) {
      console.log('⚠️ Still on login page, trying direct navigation...');
      
      // Try going directly to the analytics page
      await page.goto('http://localhost:3000/analytics/latifalshamsi', { waitUntil: 'networkidle' });
      await page.waitForTimeout(5000);
      
      console.log('📍 Direct navigation URL:', page.url());
      await page.screenshot({ path: 'step4-direct-navigation.png', fullPage: true });
    }
    
    // If we're now on the analytics page, proceed with analysis
    if (page.url().includes('/analytics/') || page.url().includes('latifalshamsi')) {
      console.log('🎉 Successfully reached analytics page!');
      
      // Wait for page to fully load
      await page.waitForTimeout(5000);
      
      console.log('\\n🔍 === COMPREHENSIVE CREATOR PAGE ANALYSIS ===\\n');
      
      // Take full page screenshot
      await page.screenshot({ path: 'analytics-page-full.png', fullPage: true });
      
      // 1. Basic page info
      console.log('📄 Page Title:', await page.title());
      console.log('📍 Final URL:', page.url());
      
      // 2. Look for profile header information
      console.log('\\n👤 === PROFILE HEADER ANALYSIS ===');
      
      const profileFields = [
        { name: 'Profile Image', selector: 'img[alt*="profile" i], .profile-image img, .avatar img, img[src*="profile"]' },
        { name: 'Username', selector: 'h1, h2, .username, [data-testid*="username"], .profile-name' },
        { name: 'Display Name', selector: '.display-name, .full-name, h2:not(:first-child), h3' },
        { name: 'Follower Count', selector: '.followers, [data-testid*="followers"], .follower-count, .metric:has-text("followers" i)' },
        { name: 'Following Count', selector: '.following, [data-testid*="following"], .following-count, .metric:has-text("following" i)' },
        { name: 'Posts Count', selector: '.posts, [data-testid*="posts"], .post-count, .metric:has-text("posts" i)' },
        { name: 'Engagement Rate', selector: '.engagement, .engagement-rate, .metric:has-text("engagement" i)' },
        { name: 'Verification Badge', selector: '.verified, .verification, [data-testid*="verified"], .badge' }
      ];
      
      for (const field of profileFields) {
        try {
          const elements = await page.locator(field.selector).all();
          if (elements.length > 0) {
            console.log(`✅ ${field.name}: Found ${elements.length} elements`);
            for (let i = 0; i < Math.min(2, elements.length); i++) {
              const text = await elements[i].textContent().catch(() => '');
              const src = await elements[i].getAttribute('src').catch(() => null);
              if (text.trim() || src) {
                console.log(`   - "${text.trim()}" ${src ? `(${src})` : ''}`);
              }
            }
          } else {
            console.log(`❌ ${field.name}: Not found`);
          }
        } catch (e) {
          console.log(`❌ ${field.name}: Error - ${e.message}`);
        }
      }
      
      // 3. Look for navigation tabs
      console.log('\\n📑 === NAVIGATION TABS ANALYSIS ===');
      
      const navSelectors = [
        'nav a, .nav-link',
        '[role="tab"], .tab',
        '.navigation a, .menu a',
        'button:has-text("Overview"), button:has-text("Posts"), button:has-text("Analytics"), button:has-text("Engagement")'
      ];
      
      let tabs = [];
      
      for (const selector of navSelectors) {
        try {
          const elements = await page.locator(selector).all();
          for (const element of elements) {
            const isVisible = await element.isVisible().catch(() => false);
            if (isVisible) {
              const text = await element.textContent().catch(() => '');
              const href = await element.getAttribute('href').catch(() => null);
              if (text.trim() && text.length < 50) { // Reasonable tab text length
                tabs.push({ text: text.trim(), href, element });
              }
            }
          }
        } catch (e) {
          // Continue to next selector
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
      
      // 4. Click through tabs and analyze content
      console.log('\\n🔄 === TAB CONTENT ANALYSIS ===');
      
      for (let i = 0; i < Math.min(5, uniqueTabs.length); i++) {
        const tab = uniqueTabs[i];
        
        try {
          console.log(`\\n🎯 Analyzing tab: "${tab.text}"`);
          
          // Click the tab
          await tab.element.click();
          await page.waitForTimeout(3000); // Wait for content to load
          
          // Take screenshot of this tab
          const filename = `tab-${i + 1}-${tab.text.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase()}.png`;
          await page.screenshot({ path: filename, fullPage: true });
          console.log(`📸 Screenshot saved: ${filename}`);
          
          // Analyze content in this tab
          const contentAnalysis = {
            metrics: [],
            charts: [],
            tables: [],
            loadingStates: [],
            errors: [],
            aiElements: []
          };
          
          // Look for metrics/stats
          const metricSelectors = [
            '.metric, .stat, .kpi',
            '.number, .count, .percentage',
            '.card .value, .card .score',
            '[data-testid*="metric"], [data-testid*="stat"]'
          ];
          
          for (const selector of metricSelectors) {
            try {
              const elements = await page.locator(selector).all();
              for (const element of elements.slice(0, 5)) { // Limit to first 5
                const text = await element.textContent().catch(() => '');
                if (text.trim() && text.length < 100) {
                  contentAnalysis.metrics.push(text.trim());
                }
              }
            } catch (e) {
              // Continue
            }
          }
          
          // Look for charts/visualizations
          const chartSelectors = [
            'canvas, svg',
            '.chart, .graph, .visualization',
            '[data-testid*="chart"], [class*="chart"]',
            '.recharts-surface, .apexcharts-canvas'
          ];
          
          for (const selector of chartSelectors) {
            try {
              const elements = await page.locator(selector).all();
              contentAnalysis.charts.push(...Array(elements.length).fill(selector));
            } catch (e) {
              // Continue
            }
          }
          
          // Look for tables
          const tableElements = await page.locator('table, .table, [role="table"]').all();
          if (tableElements.length > 0) {
            for (const table of tableElements.slice(0, 2)) {
              try {
                const headers = await table.locator('th, [role="columnheader"]').all();
                const headerTexts = [];
                for (const header of headers.slice(0, 5)) {
                  const text = await header.textContent().catch(() => '');
                  if (text.trim()) headerTexts.push(text.trim());
                }
                if (headerTexts.length > 0) {
                  contentAnalysis.tables.push(headerTexts.join(', '));
                }
              } catch (e) {
                contentAnalysis.tables.push('Table found (could not parse headers)');
              }
            }
          }
          
          // Look for loading states
          const loadingSelectors = [
            '.loading, .spinner, .skeleton',
            '[data-testid*="loading"], [class*="loading"]',
            '.animate-pulse, .animate-spin'
          ];
          
          for (const selector of loadingSelectors) {
            try {
              const elements = await page.locator(selector).all();
              if (elements.length > 0) {
                contentAnalysis.loadingStates.push(`${elements.length} ${selector}`);
              }
            } catch (e) {
              // Continue
            }
          }
          
          // Look for errors
          const errorSelectors = [
            '.error, .alert-error, .text-red',
            '[role="alert"], .warning',
            '.empty-state, .no-data'
          ];
          
          for (const selector of errorSelectors) {
            try {
              const elements = await page.locator(selector).all();
              for (const element of elements.slice(0, 3)) {
                const text = await element.textContent().catch(() => '');
                if (text.trim() && text.length < 200) {
                  contentAnalysis.errors.push(text.trim());
                }
              }
            } catch (e) {
              // Continue
            }
          }
          
          // Look for AI-related content
          const aiSelectors = [
            '.ai-analysis, .ai-insights, .sentiment',
            '[data-testid*="ai"], [class*="ai"]',
            '.content-category, .language-detection',
            '.analyzing, .processing'
          ];
          
          for (const selector of aiSelectors) {
            try {
              const elements = await page.locator(selector).all();
              for (const element of elements.slice(0, 3)) {
                const text = await element.textContent().catch(() => '');
                if (text.trim() && text.length < 200) {
                  contentAnalysis.aiElements.push(text.trim());
                }
              }
            } catch (e) {
              // Continue
            }
          }
          
          // Report findings for this tab
          console.log(`📊 Tab "${tab.text}" analysis:`);
          console.log(`   Metrics found: ${contentAnalysis.metrics.length}`);
          if (contentAnalysis.metrics.length > 0) {
            contentAnalysis.metrics.slice(0, 3).forEach(metric => {
              console.log(`     - ${metric}`);
            });
          }
          
          console.log(`   Charts found: ${contentAnalysis.charts.length}`);
          contentAnalysis.charts.slice(0, 3).forEach(chart => {
            console.log(`     - ${chart}`);
          });
          
          console.log(`   Tables found: ${contentAnalysis.tables.length}`);
          contentAnalysis.tables.forEach(table => {
            console.log(`     - Headers: ${table}`);
          });
          
          if (contentAnalysis.loadingStates.length > 0) {
            console.log(`   ⏳ Loading states: ${contentAnalysis.loadingStates.join(', ')}`);
          }
          
          if (contentAnalysis.errors.length > 0) {
            console.log(`   ⚠️ Errors/Issues:`);
            contentAnalysis.errors.forEach(error => {
              console.log(`     - ${error}`);
            });
          }
          
          if (contentAnalysis.aiElements.length > 0) {
            console.log(`   🤖 AI Elements:`);
            contentAnalysis.aiElements.forEach(ai => {
              console.log(`     - ${ai}`);
            });
          }
          
        } catch (e) {
          console.log(`❌ Error analyzing tab "${tab.text}": ${e.message}`);
        }
      }
      
      // 5. Final comprehensive summary
      console.log('\\n📋 === FINAL SUMMARY ===');
      console.log('✅ Successfully accessed and analyzed the creator analytics page');
      console.log(`📸 Generated ${uniqueTabs.length + 4} screenshots for analysis`);
      console.log('🎯 Focused analysis on latifalshamsi profile');
      
    } else {
      console.log('❌ Could not access analytics page. Current URL:', page.url());
      console.log('This might be due to authentication issues or the page structure.');
    }
    
    // Take final screenshot regardless of success
    await page.screenshot({ path: 'final-state.png', fullPage: true });
    console.log('📸 Final state screenshot saved');
    
  } catch (error) {
    console.error('❌ Error during analysis:', error);
    await page.screenshot({ path: 'error-state.png', fullPage: true });
  } finally {
    console.log('🏁 Closing browser...');
    await browser.close();
    console.log('✅ Analysis complete! Check all generated PNG files for detailed visual analysis.');
  }
})();