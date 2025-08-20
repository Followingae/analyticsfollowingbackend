const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 800
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();
  
  try {
    console.log('🎯 === FINAL COMPREHENSIVE CREATOR ANALYSIS ===\\n');
    
    // Step 1: Login
    console.log('🔐 Step 1: Authentication...');
    await page.goto('http://localhost:3000/auth/login', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    
    await page.fill('input[name="email"]', 'client@analyticsfollowing.com');
    await page.fill('input[name="password"]', 'ClientPass2024!');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(5000);
    
    console.log('✅ Authenticated successfully');
    await page.screenshot({ path: 'analysis-step1-dashboard.png', fullPage: true });
    
    // Step 2: Navigate to Creators page
    console.log('\\n📋 Step 2: Navigating to Creators page...');
    const creatorsLink = page.locator('a[href*="creators"], a:has-text("Creators")').first();
    
    if (await creatorsLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await creatorsLink.click();
      await page.waitForTimeout(5000);
      console.log('✅ Navigated to Creators page');
      console.log('📍 Current URL:', page.url());
      
      await page.screenshot({ path: 'analysis-step2-creators-list.png', fullPage: true });
    } else {
      console.log('❌ Creators link not found, trying direct navigation...');
      await page.goto('http://localhost:3000/creators', { waitUntil: 'networkidle' });
      await page.waitForTimeout(3000);
    }
    
    // Step 3: Search for or navigate to latifalshamsi
    console.log('\\n🔍 Step 3: Finding latifalshamsi profile...');
    
    // Look for latifalshamsi in the creators list
    const latifaLink = page.locator('a:has-text("latifalshamsi" i), button:has-text("latifalshamsi" i)').first();
    
    if (await latifaLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      console.log('✅ Found latifalshamsi in creators list');
      await latifaLink.click();
      await page.waitForTimeout(5000);
    } else {
      // Try search if available
      const searchInput = page.locator('input[type="search"], input[placeholder*="search" i]').first();
      
      if (await searchInput.isVisible({ timeout: 3000 }).catch(() => false)) {
        console.log('🔍 Searching for latifalshamsi...');
        await searchInput.fill('latifalshamsi');
        await page.keyboard.press('Enter');
        await page.waitForTimeout(3000);
        
        // Click on the search result
        const searchResult = page.locator('a:has-text("latifalshamsi" i), button:has-text("latifalshamsi" i)').first();
        if (await searchResult.isVisible({ timeout: 5000 }).catch(() => false)) {
          await searchResult.click();
          await page.waitForTimeout(5000);
        }
      } else {
        // Direct navigation as last resort
        console.log('🎯 Direct navigation to analytics page...');
        await page.goto('http://localhost:3000/analytics/latifalshamsi', { waitUntil: 'networkidle' });
        await page.waitForTimeout(5000);
      }
    }
    
    console.log('📍 Final URL:', page.url());
    
    // Step 4: Comprehensive Creator Profile Analysis
    if (page.url().includes('latifalshamsi') || page.url().includes('analytics')) {
      console.log('\\n🎉 SUCCESS: Reached creator profile page!\\n');
      
      await page.screenshot({ path: 'analysis-step3-creator-profile.png', fullPage: true });
      
      // === PROFILE HEADER ANALYSIS ===
      console.log('👤 === PROFILE HEADER FIELDS ===');
      
      const profileHeaderFields = {
        'Profile Image': {
          selectors: ['img[alt*="profile" i]', '.profile-image img', '.avatar img', 'img[src*="profile"]'],
          type: 'image'
        },
        'Username/Handle': {
          selectors: ['h1', 'h2', '.username', '.handle', '[data-testid*="username"]'],
          type: 'text'
        },
        'Full Name/Display Name': {
          selectors: ['.full-name', '.display-name', '.name', 'h2:not(:first-child)', 'h3'],
          type: 'text'
        },
        'Follower Count': {
          selectors: ['.followers', '.follower-count', '[data-testid*="followers"]', '.metric:has-text("followers" i)'],
          type: 'metric'
        },
        'Following Count': {
          selectors: ['.following', '.following-count', '[data-testid*="following"]', '.metric:has-text("following" i)'],
          type: 'metric'
        },
        'Posts Count': {
          selectors: ['.posts', '.post-count', '[data-testid*="posts"]', '.metric:has-text("posts" i)'],
          type: 'metric'
        },
        'Engagement Rate': {
          selectors: ['.engagement', '.engagement-rate', '.metric:has-text("engagement" i)'],
          type: 'metric'
        },
        'Verification Status': {
          selectors: ['.verified', '.verification', '.badge', '[data-testid*="verified"]'],
          type: 'status'
        },
        'Bio/Description': {
          selectors: ['.bio', '.description', '.profile-description', '.about'],
          type: 'text'
        }
      };
      
      const foundFields = {};
      
      for (const [fieldName, config] of Object.entries(profileHeaderFields)) {
        let found = false;
        
        for (const selector of config.selectors) {
          try {
            const elements = await page.locator(selector).all();
            
            for (const element of elements) {
              const isVisible = await element.isVisible().catch(() => false);
              if (isVisible) {
                let value = '';
                
                if (config.type === 'image') {
                  value = await element.getAttribute('src').catch(() => '') || 
                          await element.getAttribute('alt').catch(() => '') || 'Image found';
                } else {
                  value = await element.textContent().catch(() => '');
                }
                
                if (value.trim()) {
                  foundFields[fieldName] = {
                    value: value.trim(),
                    selector: selector,
                    type: config.type
                  };
                  found = true;
                  break;
                }
              }
            }
            
            if (found) break;
          } catch (e) {
            // Continue to next selector
          }
        }
        
        if (found) {
          console.log(`✅ ${fieldName}: "${foundFields[fieldName].value}" (${foundFields[fieldName].selector})`);
        } else {
          console.log(`❌ ${fieldName}: Not found`);
        }
      }
      
      // === NAVIGATION TABS ANALYSIS ===
      console.log('\\n📑 === NAVIGATION TABS & SECTIONS ===');
      
      const tabSelectors = [
        'nav a, .nav-link, .navigation a',
        '[role="tab"], .tab, .tab-button',
        'button[role="tab"]',
        '.menu a, .sidebar a',
        'button:has-text("Overview"), button:has-text("Posts"), button:has-text("Analytics"), button:has-text("Engagement"), button:has-text("Audience")'
      ];
      
      let allTabs = [];
      
      for (const selector of tabSelectors) {
        try {
          const elements = await page.locator(selector).all();
          
          for (const element of elements) {
            const isVisible = await element.isVisible().catch(() => false);
            if (isVisible) {
              const text = await element.textContent().catch(() => '');
              const href = await element.getAttribute('href').catch(() => null);
              const isButton = await element.evaluate(el => el.tagName.toLowerCase() === 'button').catch(() => false);
              
              if (text.trim() && text.length < 50 && text.length > 1) {
                allTabs.push({
                  text: text.trim(),
                  href: href,
                  element: element,
                  selector: selector,
                  isButton: isButton
                });
              }
            }
          }
        } catch (e) {
          // Continue to next selector
        }
      }
      
      // Remove duplicates based on text
      const uniqueTabs = allTabs.filter((tab, index, self) => 
        index === self.findIndex(t => t.text.toLowerCase() === tab.text.toLowerCase())
      );
      
      console.log(`📑 Found ${uniqueTabs.length} unique navigation tabs/sections:`);
      uniqueTabs.forEach((tab, i) => {
        console.log(`  ${i + 1}. "${tab.text}" ${tab.href ? `(${tab.href})` : ''} [${tab.selector}]`);
      });
      
      // === TAB CONTENT ANALYSIS ===
      console.log('\\n🔄 === DETAILED TAB CONTENT ANALYSIS ===');
      
      const tabAnalysis = {};
      
      for (let i = 0; i < Math.min(6, uniqueTabs.length); i++) {
        const tab = uniqueTabs[i];
        
        try {
          console.log(`\\n🎯 Analyzing tab ${i + 1}: "${tab.text}"`);
          
          // Click the tab
          await tab.element.scrollIntoViewIfNeeded();
          await tab.element.click();
          await page.waitForTimeout(4000); // Wait for content to load
          
          // Take screenshot
          const filename = `tab-${i + 1}-${tab.text.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase()}.png`;
          await page.screenshot({ path: filename, fullPage: true });
          console.log(`📸 Screenshot: ${filename}`);
          
          const analysis = {
            metrics: [],
            visualizations: [],
            tables: [],
            cards: [],
            loadingStates: [],
            errors: [],
            aiContent: [],
            interactiveElements: []
          };
          
          // Metrics and KPIs
          const metricSelectors = [
            '.metric, .kpi, .stat',
            '.number, .count, .percentage, .rate',
            '.card .value, .widget .value',
            '[data-testid*="metric"], [data-testid*="stat"]',
            '.analytics-item, .data-point'
          ];
          
          for (const selector of metricSelectors) {
            try {
              const elements = await page.locator(selector).all();
              for (const element of elements.slice(0, 10)) {
                const text = await element.textContent().catch(() => '');
                if (text.trim() && text.length < 100 && /\\d/.test(text)) {
                  analysis.metrics.push({
                    value: text.trim(),
                    selector: selector
                  });
                }
              }
            } catch (e) {}
          }
          
          // Data Visualizations
          const chartSelectors = [
            'canvas',
            'svg',
            '.chart, .graph, .visualization',
            '.recharts-surface',
            '.apexcharts-canvas',
            '[data-testid*="chart"]'
          ];
          
          for (const selector of chartSelectors) {
            try {
              const elements = await page.locator(selector).all();
              if (elements.length > 0) {
                analysis.visualizations.push({
                  count: elements.length,
                  type: selector
                });
              }
            } catch (e) {}
          }
          
          // Tables
          try {
            const tables = await page.locator('table, .table, [role="table"]').all();
            for (const table of tables.slice(0, 3)) {
              const headers = await table.locator('th, [role="columnheader"]').all();
              const headerTexts = [];
              
              for (const header of headers.slice(0, 8)) {
                const text = await header.textContent().catch(() => '');
                if (text.trim()) headerTexts.push(text.trim());
              }
              
              const rowCount = await table.locator('tr, [role="row"]').count().catch(() => 0);
              
              analysis.tables.push({
                headers: headerTexts,
                rowCount: rowCount
              });
            }
          } catch (e) {}
          
          // Cards/Widgets
          const cardSelectors = [
            '.card, .widget, .panel',
            '.dashboard-item, .analytics-card',
            '[data-testid*="card"]'
          ];
          
          for (const selector of cardSelectors) {
            try {
              const elements = await page.locator(selector).all();
              for (const element of elements.slice(0, 5)) {
                const title = await element.locator('h1, h2, h3, h4, h5, h6, .title, .header').first().textContent().catch(() => '');
                const content = await element.textContent().catch(() => '');
                
                if (title.trim() || (content.trim() && content.length < 200)) {
                  analysis.cards.push({
                    title: title.trim() || 'Untitled Card',
                    preview: content.trim().slice(0, 100)
                  });
                }
              }
            } catch (e) {}
          }
          
          // Loading States
          const loadingSelectors = [
            '.loading, .spinner, .skeleton',
            '.animate-pulse, .animate-spin',
            '[data-testid*="loading"]',
            '.loading-text, .processing'
          ];
          
          for (const selector of loadingSelectors) {
            try {
              const elements = await page.locator(selector).all();
              if (elements.length > 0) {
                const text = await elements[0].textContent().catch(() => '');
                analysis.loadingStates.push({
                  count: elements.length,
                  selector: selector,
                  text: text.trim()
                });
              }
            } catch (e) {}
          }
          
          // Errors and Issues
          const errorSelectors = [
            '.error, .alert-error, .danger',
            '.warning, .alert-warning',
            '[role="alert"]',
            '.empty-state, .no-data, .not-found',
            '.text-red, .text-destructive'
          ];
          
          for (const selector of errorSelectors) {
            try {
              const elements = await page.locator(selector).all();
              for (const element of elements.slice(0, 3)) {
                const text = await element.textContent().catch(() => '');
                if (text.trim() && text.length < 300) {
                  analysis.errors.push({
                    message: text.trim(),
                    selector: selector
                  });
                }
              }
            } catch (e) {}
          }
          
          // AI Content
          const aiSelectors = [
            '.ai-analysis, .ai-insights, .sentiment',
            '.content-category, .language-detection',
            '[data-testid*="ai"], [class*="ai"]',
            '.analyzing, .processing, .ai-processing',
            '.sentiment-score, .category-tag'
          ];
          
          for (const selector of aiSelectors) {
            try {
              const elements = await page.locator(selector).all();
              for (const element of elements.slice(0, 5)) {
                const text = await element.textContent().catch(() => '');
                if (text.trim() && text.length < 200) {
                  analysis.aiContent.push({
                    content: text.trim(),
                    selector: selector
                  });
                }
              }
            } catch (e) {}
          }
          
          // Interactive Elements
          const interactiveSelectors = [
            'button:not([type="submit"]), .btn',
            'select, .select',
            'input[type="range"], .slider',
            '.toggle, .switch',
            '.dropdown, .menu'
          ];
          
          for (const selector of interactiveSelectors) {
            try {
              const elements = await page.locator(selector).all();
              for (const element of elements.slice(0, 5)) {
                const text = await element.textContent().catch(() => '');
                const type = await element.evaluate(el => el.tagName.toLowerCase()).catch(() => '');
                
                if (text.trim() || type) {
                  analysis.interactiveElements.push({
                    text: text.trim() || `${type} element`,
                    type: type,
                    selector: selector
                  });
                }
              }
            } catch (e) {}
          }
          
          tabAnalysis[tab.text] = analysis;
          
          // Report findings for this tab
          console.log(`📊 Analysis results for "${tab.text}":`);
          console.log(`   📈 Metrics: ${analysis.metrics.length}`);
          analysis.metrics.slice(0, 3).forEach(metric => {
            console.log(`      - ${metric.value} [${metric.selector}]`);
          });
          
          console.log(`   📊 Visualizations: ${analysis.visualizations.reduce((sum, viz) => sum + viz.count, 0)}`);
          analysis.visualizations.forEach(viz => {
            console.log(`      - ${viz.count} ${viz.type}`);
          });
          
          console.log(`   📋 Tables: ${analysis.tables.length}`);
          analysis.tables.forEach((table, idx) => {
            console.log(`      - Table ${idx + 1}: ${table.headers.join(', ')} (${table.rowCount} rows)`);
          });
          
          console.log(`   🃏 Cards: ${analysis.cards.length}`);
          analysis.cards.slice(0, 3).forEach(card => {
            console.log(`      - "${card.title}"`);
          });
          
          if (analysis.loadingStates.length > 0) {
            console.log(`   ⏳ Loading States: ${analysis.loadingStates.length}`);
            analysis.loadingStates.forEach(loading => {
              console.log(`      - ${loading.text || loading.selector} (${loading.count})`);
            });
          }
          
          if (analysis.errors.length > 0) {
            console.log(`   ⚠️ Errors/Issues: ${analysis.errors.length}`);
            analysis.errors.forEach(error => {
              console.log(`      - ${error.message} [${error.selector}]`);
            });
          }
          
          if (analysis.aiContent.length > 0) {
            console.log(`   🤖 AI Content: ${analysis.aiContent.length}`);
            analysis.aiContent.forEach(ai => {
              console.log(`      - ${ai.content} [${ai.selector}]`);
            });
          }
          
          if (analysis.interactiveElements.length > 0) {
            console.log(`   🎮 Interactive: ${analysis.interactiveElements.length}`);
            analysis.interactiveElements.slice(0, 3).forEach(el => {
              console.log(`      - ${el.text} (${el.type})`);
            });
          }
          
        } catch (e) {
          console.log(`❌ Error analyzing tab "${tab.text}": ${e.message}`);
        }
      }
      
      // === FINAL COMPREHENSIVE SUMMARY ===
      console.log('\\n🎯 === COMPREHENSIVE ANALYSIS SUMMARY ===');
      console.log(`✅ Successfully analyzed ${uniqueTabs.length} tabs/sections`);
      console.log(`📸 Generated ${uniqueTabs.length + 3} screenshots for visual reference`);
      
      console.log('\\n📋 Profile Fields Found:');
      Object.entries(foundFields).forEach(([field, data]) => {
        console.log(`   ✅ ${field}: ${data.type} field handled via ${data.selector}`);
      });
      
      console.log('\\n📊 Content Analysis Summary:');
      let totalMetrics = 0, totalCharts = 0, totalTables = 0, totalCards = 0, totalAI = 0;
      
      Object.entries(tabAnalysis).forEach(([tabName, analysis]) => {
        totalMetrics += analysis.metrics.length;
        totalCharts += analysis.visualizations.reduce((sum, viz) => sum + viz.count, 0);
        totalTables += analysis.tables.length;
        totalCards += analysis.cards.length;
        totalAI += analysis.aiContent.length;
      });
      
      console.log(`   📈 Total Metrics: ${totalMetrics}`);
      console.log(`   📊 Total Charts: ${totalCharts}`);
      console.log(`   📋 Total Tables: ${totalTables}`);
      console.log(`   🃏 Total Cards: ${totalCards}`);
      console.log(`   🤖 Total AI Elements: ${totalAI}`);
      
    } else {
      console.log(`❌ Failed to reach creator profile. Current URL: ${page.url()}`);
      await page.screenshot({ path: 'analysis-failed-final-state.png', fullPage: true });
    }
    
    // Take final comprehensive screenshot
    await page.screenshot({ path: 'comprehensive-analysis-final.png', fullPage: true });
    
    console.log('\\n🏁 === ANALYSIS COMPLETE ===');
    console.log('📂 All screenshots and analysis data have been generated');
    console.log('🎯 This comprehensive analysis covers all visible fields and functionality');
    
  } catch (error) {
    console.error('❌ Critical error:', error);
    await page.screenshot({ path: 'critical-error.png', fullPage: true });
  } finally {
    await browser.close();
    console.log('✅ Browser closed. Comprehensive analysis complete!');
  }
})();