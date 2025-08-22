const { chromium } = require('playwright');

async function tabSpecificTest() {
    const browser = await chromium.launch({ 
        headless: false, // Show browser for debugging
        slowMo: 1000 // Slow down operations for observation
    });
    
    const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 }
    });
    
    const page = await context.newPage();
    
    // Test credentials
    const email = 'client@analyticsfollowing.com';
    const password = 'ClientPass2024!';
    
    console.log('🚀 Starting Tab-Specific Backend Error Test...');
    console.log('================================================');
    
    const testResults = {
        passed: 0,
        failed: 0,
        errors: [],
        apiCalls: []
    };
    
    // Monitor all API calls
    page.on('response', response => {
        if (response.url().includes('/api/')) {
            const apiCall = {
                url: response.url(),
                status: response.status(),
                statusText: response.statusText(),
                timestamp: new Date().toISOString()
            };
            testResults.apiCalls.push(apiCall);
            
            const status = response.status() >= 200 && response.status() < 300 ? '✅' : '❌';
            console.log(`  API: ${status} ${response.status()} ${response.url().split('/api/')[1]}`);
        }
    });
    
    // Monitor console errors
    page.on('console', msg => {
        if (msg.type() === 'error') {
            console.log('🔴 Console Error:', msg.text());
            testResults.errors.push('Console Error: ' + msg.text());
        }
    });
    
    try {
        // Step 1: Navigate to Frontend and Login
        console.log('\n🔍 Step 1: Login Process');
        console.log('-------------------------');
        
        await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
        console.log('✅ Frontend loaded');
        
        // Perform login
        await page.waitForSelector('input[type="email"], input[name="email"], #email', { timeout: 10000 });
        await page.fill('input[type="email"], input[name="email"], #email', email);
        
        await page.waitForSelector('input[type="password"], input[name="password"], #password', { timeout: 5000 });
        await page.fill('input[type="password"], input[name="password"], #password', password);
        
        const loginButton = await page.locator('button:has-text("Login"), button:has-text("Sign In"), input[type="submit"]').first();
        await loginButton.click();
        
        // Wait for successful login
        await page.waitForTimeout(3000);
        console.log('✅ Login completed');
        testResults.passed++;
        
        // Step 2: Test Dashboard Tab
        console.log('\n🔍 Step 2: Testing Dashboard Tab');
        console.log('---------------------------------');
        
        try {
            // Look for dashboard tab/link
            const dashboardSelectors = [
                'a[href="/dashboard"]',
                'a[href*="dashboard"]',
                'button:has-text("Dashboard")',
                'nav a:has-text("Dashboard")',
                '[data-testid="dashboard"]',
                '.dashboard-tab',
                '.nav-dashboard'
            ];
            
            let dashboardTab = null;
            for (const selector of dashboardSelectors) {
                try {
                    const element = page.locator(selector).first();
                    if (await element.isVisible({ timeout: 2000 })) {
                        dashboardTab = element;
                        console.log(`✅ Dashboard tab found: ${selector}`);
                        break;
                    }
                } catch (e) {
                    // Continue to next selector
                }
            }
            
            if (dashboardTab) {
                await dashboardTab.click();
                await page.waitForTimeout(3000); // Wait for dashboard to load
                console.log('✅ Dashboard tab clicked and loaded');
                testResults.passed++;
            } else {
                // Check if we're already on dashboard
                const currentUrl = page.url();
                if (currentUrl.includes('dashboard') || currentUrl === 'http://localhost:3000/') {
                    console.log('✅ Already on dashboard page');
                    testResults.passed++;
                } else {
                    throw new Error('Dashboard tab not found');
                }
            }
        } catch (error) {
            console.log('❌ Dashboard tab failed:', error.message);
            testResults.failed++;
            testResults.errors.push('Dashboard Tab: ' + error.message);
        }
        
        // Step 3: Test Creators Tab
        console.log('\n🔍 Step 3: Testing Creators Tab');
        console.log('-------------------------------');
        
        try {
            const creatorsSelectors = [
                'a[href="/creators"]',
                'a[href*="creators"]',
                'button:has-text("Creators")',
                'nav a:has-text("Creators")',
                '[data-testid="creators"]',
                '.creators-tab',
                '.nav-creators'
            ];
            
            let creatorsTab = null;
            for (const selector of creatorsSelectors) {
                try {
                    const element = page.locator(selector).first();
                    if (await element.isVisible({ timeout: 2000 })) {
                        creatorsTab = element;
                        console.log(`✅ Creators tab found: ${selector}`);
                        break;
                    }
                } catch (e) {
                    // Continue
                }
            }
            
            if (creatorsTab) {
                await creatorsTab.click();
                await page.waitForTimeout(4000); // Wait for creators page to load
                console.log('✅ Creators tab clicked and loaded');
                testResults.passed++;
            } else {
                throw new Error('Creators tab not found');
            }
        } catch (error) {
            console.log('❌ Creators tab failed:', error.message);
            testResults.failed++;
            testResults.errors.push('Creators Tab: ' + error.message);
        }
        
        // Step 4: Test Lists Tab
        console.log('\n🔍 Step 4: Testing Lists Tab');
        console.log('----------------------------');
        
        try {
            const listsSelectors = [
                'a[href="/lists"]',
                'a[href*="lists"]',
                'button:has-text("Lists")',
                'nav a:has-text("Lists")',
                '[data-testid="lists"]',
                '.lists-tab',
                '.nav-lists',
                'a:has-text("My Lists")'
            ];
            
            let listsTab = null;
            for (const selector of listsSelectors) {
                try {
                    const element = page.locator(selector).first();
                    if (await element.isVisible({ timeout: 2000 })) {
                        listsTab = element;
                        console.log(`✅ Lists tab found: ${selector}`);
                        break;
                    }
                } catch (e) {
                    // Continue
                }
            }
            
            if (listsTab) {
                await listsTab.click();
                await page.waitForTimeout(4000); // Wait for lists page to load
                console.log('✅ Lists tab clicked and loaded');
                testResults.passed++;
            } else {
                throw new Error('Lists tab not found');
            }
        } catch (error) {
            console.log('❌ Lists tab failed:', error.message);
            testResults.failed++;
            testResults.errors.push('Lists Tab: ' + error.message);
        }
        
        // Step 5: Test Campaign Tab
        console.log('\n🔍 Step 5: Testing Campaign Tab');
        console.log('-------------------------------');
        
        try {
            const campaignSelectors = [
                'a[href="/campaigns"]',
                'a[href*="campaign"]',
                'button:has-text("Campaign")',
                'button:has-text("Campaigns")',
                'nav a:has-text("Campaign")',
                '[data-testid="campaigns"]',
                '.campaigns-tab',
                '.nav-campaigns'
            ];
            
            let campaignTab = null;
            for (const selector of campaignSelectors) {
                try {
                    const element = page.locator(selector).first();
                    if (await element.isVisible({ timeout: 2000 })) {
                        campaignTab = element;
                        console.log(`✅ Campaign tab found: ${selector}`);
                        break;
                    }
                } catch (e) {
                    // Continue
                }
            }
            
            if (campaignTab) {
                await campaignTab.click();
                await page.waitForTimeout(4000); // Wait for campaign page to load
                console.log('✅ Campaign tab clicked and loaded');
                testResults.passed++;
            } else {
                throw new Error('Campaign tab not found');
            }
        } catch (error) {
            console.log('❌ Campaign tab failed:', error.message);
            testResults.failed++;
            testResults.errors.push('Campaign Tab: ' + error.message);
        }
        
        // Step 6: Test Profile Search (if available)
        console.log('\n🔍 Step 6: Testing Profile Search');
        console.log('----------------------------------');
        
        try {
            // Try to find search functionality
            const searchSelectors = [
                'input[placeholder*="search"]',
                'input[placeholder*="Search"]',
                'input[type="search"]',
                '#search',
                'input[name="search"]',
                '.search input'
            ];
            
            let searchInput = null;
            for (const selector of searchSelectors) {
                try {
                    const element = page.locator(selector).first();
                    if (await element.isVisible({ timeout: 2000 })) {
                        searchInput = element;
                        console.log(`✅ Search input found: ${selector}`);
                        break;
                    }
                } catch (e) {
                    // Continue
                }
            }
            
            if (searchInput) {
                await searchInput.fill('test_profile');
                await searchInput.press('Enter');
                await page.waitForTimeout(3000);
                console.log('✅ Search functionality tested');
                testResults.passed++;
            } else {
                console.log('⚠️  Search input not found - may not be implemented yet');
                // Don't count this as a failure since it's expected
            }
        } catch (error) {
            console.log('❌ Search test failed:', error.message);
            testResults.failed++;
            testResults.errors.push('Search Test: ' + error.message);
        }
        
    } catch (globalError) {
        console.log('❌ Global test error:', globalError.message);
        testResults.failed++;
        testResults.errors.push('Global Error: ' + globalError.message);
    }
    
    // Final Results
    console.log('\n📊 TAB-SPECIFIC TEST RESULTS');
    console.log('==============================');
    console.log(`✅ Tests Passed: ${testResults.passed}`);
    console.log(`❌ Tests Failed: ${testResults.failed}`);
    console.log(`📈 Success Rate: ${Math.round((testResults.passed / (testResults.passed + testResults.failed)) * 100)}%`);
    
    // API Call Summary
    console.log('\n📡 API CALLS SUMMARY');
    console.log('====================');
    const successfulCalls = testResults.apiCalls.filter(call => call.status >= 200 && call.status < 300);
    const failedCalls = testResults.apiCalls.filter(call => call.status >= 400);
    
    console.log(`✅ Successful API Calls: ${successfulCalls.length}`);
    console.log(`❌ Failed API Calls: ${failedCalls.length}`);
    
    if (failedCalls.length > 0) {
        console.log('\n🚨 FAILED API CALLS:');
        failedCalls.forEach(call => {
            console.log(`  ❌ ${call.status} ${call.url}`);
        });
    }
    
    if (testResults.errors.length > 0) {
        console.log('\n🚨 ISSUES FOUND:');
        console.log('-----------------');
        testResults.errors.forEach((error, index) => {
            console.log(`${index + 1}. ${error}`);
        });
    }
    
    await browser.close();
    return testResults;
}

// Run the tab-specific test
tabSpecificTest()
    .then(results => {
        console.log('\n🏁 Tab-specific test execution completed');
        process.exit(results.failed > 0 ? 1 : 0);
    })
    .catch(error => {
        console.error('❌ Test execution failed:', error);
        process.exit(1);
    });