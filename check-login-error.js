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
    console.log('🔍 Checking login error message...');
    
    await page.goto('http://localhost:3000/auth/login', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    
    // Fill the form
    await page.fill('input[type="email"]', 'client@analyticsfollowing.com');
    await page.fill('input[type="password"]', 'ClientPass2024!');
    
    console.log('📧 Form filled, clicking submit...');
    
    // Click submit and wait
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);
    
    // Check for error messages
    const alertElements = await page.locator('[role="alert"]').all();
    console.log(`⚠️ Found ${alertElements.length} alert elements`);
    
    for (let i = 0; i < alertElements.length; i++) {
      const alert = alertElements[i];
      const text = await alert.textContent().catch(() => '');
      const innerHTML = await alert.innerHTML().catch(() => '');
      
      console.log(`Alert ${i + 1}:`);
      console.log(`  Text: "${text.trim()}"`);
      console.log(`  HTML: "${innerHTML}"`);
    }
    
    // Check all visible text on page for clues
    console.log('\\n📄 All visible text on page:');
    const bodyText = await page.textContent('body');
    console.log(bodyText.slice(0, 1000) + '...');
    
    // Take final screenshot
    await page.screenshot({ path: 'login-error-analysis.png', fullPage: true });
    console.log('\\n📸 Login error analysis screenshot saved');
    
  } catch (error) {
    console.error('❌ Error:', error);
  } finally {
    await browser.close();
  }
})();