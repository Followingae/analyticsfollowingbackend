const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 2000 // Very slow for debugging
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();
  
  try {
    console.log('🔍 Debug: Analyzing login form...');
    
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    
    console.log('📍 Current URL:', page.url());
    
    // Take initial screenshot
    await page.screenshot({ path: 'debug-initial.png', fullPage: true });
    console.log('📸 Initial page screenshot saved');
    
    // Look for all input elements
    const allInputs = await page.locator('input').all();
    console.log(`🔍 Found ${allInputs.length} input elements`);
    
    for (let i = 0; i < allInputs.length; i++) {
      const input = allInputs[i];
      const type = await input.getAttribute('type').catch(() => 'unknown');
      const name = await input.getAttribute('name').catch(() => 'no-name');
      const placeholder = await input.getAttribute('placeholder').catch(() => 'no-placeholder');
      const id = await input.getAttribute('id').catch(() => 'no-id');
      
      console.log(`  Input ${i + 1}: type="${type}" name="${name}" placeholder="${placeholder}" id="${id}"`);
    }
    
    // Look for all buttons
    const allButtons = await page.locator('button').all();
    console.log(`\\n🔍 Found ${allButtons.length} button elements`);
    
    for (let i = 0; i < allButtons.length; i++) {
      const button = allButtons[i];
      const text = await button.textContent().catch(() => '');
      const type = await button.getAttribute('type').catch(() => 'unknown');
      const className = await button.getAttribute('class').catch(() => 'no-class');
      
      console.log(`  Button ${i + 1}: text="${text.trim()}" type="${type}" class="${className}"`);
    }
    
    // Try to fill the form more specifically
    console.log('\\n🔐 Attempting login with specific selectors...');
    
    // Try different email input selectors
    const emailSelectors = [
      'input[type="email"]',
      'input[name="email"]',
      'input[id*="email"]',
      'input[placeholder*="email" i]',
      'input[autocomplete="email"]'
    ];
    
    let emailFilled = false;
    for (const selector of emailSelectors) {
      try {
        const emailInput = page.locator(selector).first();
        if (await emailInput.isVisible({ timeout: 2000 }).catch(() => false)) {
          console.log(`📧 Found email input with: ${selector}`);
          await emailInput.click();
          await emailInput.fill('client@analyticsfollowing.com');
          emailFilled = true;
          break;
        }
      } catch (e) {
        // Continue
      }
    }
    
    // Try password input
    const passwordSelectors = [
      'input[type="password"]',
      'input[name="password"]',
      'input[id*="password"]',
      'input[placeholder*="password" i]',
      'input[autocomplete="current-password"]'
    ];
    
    let passwordFilled = false;
    for (const selector of passwordSelectors) {
      try {
        const passwordInput = page.locator(selector).first();
        if (await passwordInput.isVisible({ timeout: 2000 }).catch(() => false)) {
          console.log(`🔑 Found password input with: ${selector}`);
          await passwordInput.click();
          await passwordInput.fill('ClientPass2024!');
          passwordFilled = true;
          break;
        }
      } catch (e) {
        // Continue
      }
    }
    
    console.log(`\\n📋 Form status: Email filled: ${emailFilled}, Password filled: ${passwordFilled}`);
    
    // Take screenshot after filling
    await page.screenshot({ path: 'debug-form-filled.png', fullPage: true });
    console.log('📸 Form filled screenshot saved');
    
    // Try to submit
    const submitSelectors = [
      'button[type="submit"]',
      'button:has-text("Login" i)',
      'button:has-text("Sign in" i)',
      'button:has-text("Continue" i)',
      'input[type="submit"]',
      'form button'
    ];
    
    let submitted = false;
    for (const selector of submitSelectors) {
      try {
        const submitButton = page.locator(selector).first();
        if (await submitButton.isVisible({ timeout: 2000 }).catch(() => false)) {
          const buttonText = await submitButton.textContent().catch(() => '');
          console.log(`✅ Found submit button with: ${selector} (text: "${buttonText.trim()}")`);
          
          // Click the button
          await submitButton.click();
          submitted = true;
          console.log('🔄 Button clicked, waiting for response...');
          
          // Wait for navigation or response
          await page.waitForTimeout(5000);
          
          console.log('📍 URL after submit:', page.url());
          
          // Take screenshot after submit
          await page.screenshot({ path: 'debug-after-submit.png', fullPage: true });
          console.log('📸 After submit screenshot saved');
          
          break;
        }
      } catch (e) {
        console.log(`❌ Error with selector ${selector}:`, e.message);
      }
    }
    
    if (!submitted) {
      console.log('❌ Could not find or click submit button');
    }
    
    // Check for any error messages
    const errorSelectors = [
      '.error, .alert-error',
      '.warning, .alert-warning', 
      '[role="alert"]',
      '.message, .notification',
      '.invalid, .validation-error'
    ];
    
    console.log('\\n⚠️ Checking for error messages...');
    for (const selector of errorSelectors) {
      try {
        const errors = await page.locator(selector).all();
        if (errors.length > 0) {
          console.log(`⚠️ Found ${errors.length} error elements with: ${selector}`);
          for (const error of errors.slice(0, 3)) {
            const text = await error.textContent().catch(() => '');
            if (text.trim()) {
              console.log(`  - "${text.trim()}"`);
            }
          }
        }
      } catch (e) {
        // Continue
      }
    }
    
    console.log('\\n🏁 Debug complete. Check the debug-*.png files for visual analysis.');
    
  } catch (error) {
    console.error('❌ Debug error:', error);
    await page.screenshot({ path: 'debug-error.png', fullPage: true });
  } finally {
    await browser.close();
  }
})();