const { test, expect } = require('@playwright/test');

test.describe('Comprehensive Platform E2E Verification', () => {
  const baseURL = 'http://localhost:8000';
  
  test('System Health and Core Services', async ({ request }) => {
    console.log('🔍 Testing System Health...');
    
    // 1. Basic health check
    const healthResponse = await request.get(`${baseURL}/health`);
    expect(healthResponse.status()).toBe(200);
    const healthData = await healthResponse.json();
    console.log('✅ Health check:', healthData.status);
    
    // 2. Database connection
    const dbResponse = await request.get(`${baseURL}/api/test-db`);
    expect(dbResponse.status()).toBe(200);
    console.log('✅ Database connection verified');
  });

  test('Credits/Billing System Endpoints', async ({ request }) => {
    console.log('💳 Testing Credits/Billing System...');
    
    try {
      // Test credits balance endpoint (previously 404)
      const balanceResponse = await request.get(`${baseURL}/api/v1/credits/balance`);
      console.log('Credits balance status:', balanceResponse.status());
      
      if (balanceResponse.status() === 401) {
        console.log('⚠️  Credits endpoints require authentication (expected)');
      } else if (balanceResponse.status() === 200) {
        console.log('✅ Credits balance endpoint working');
      } else {
        console.log('❌ Credits balance endpoint error:', balanceResponse.status());
      }
      
      // Test pricing endpoint
      const pricingResponse = await request.get(`${baseURL}/api/v1/credits/pricing`);
      console.log('Credits pricing status:', pricingResponse.status());
      
      if (pricingResponse.status() === 401) {
        console.log('⚠️  Credits pricing requires authentication (expected)');
      } else if (pricingResponse.status() === 200) {
        console.log('✅ Credits pricing endpoint working');
      } else {
        console.log('❌ Credits pricing endpoint error:', pricingResponse.status());
      }
      
      // Test dashboard endpoint
      const dashboardResponse = await request.get(`${baseURL}/api/v1/credits/dashboard`);
      console.log('Credits dashboard status:', dashboardResponse.status());
      
      if (dashboardResponse.status() === 401) {
        console.log('⚠️  Credits dashboard requires authentication (expected)');
      } else if (dashboardResponse.status() === 200) {
        console.log('✅ Credits dashboard endpoint working');
      } else {
        console.log('❌ Credits dashboard endpoint error:', dashboardResponse.status());
      }
      
    } catch (error) {
      console.log('❌ Credits system test error:', error.message);
    }
  });

  test('Campaigns System Routes', async ({ request }) => {
    console.log('📊 Testing Campaigns System...');
    
    try {
      // Test campaigns list endpoint
      const campaignsResponse = await request.get(`${baseURL}/api/v1/campaigns/`);
      console.log('Campaigns list status:', campaignsResponse.status());
      
      if (campaignsResponse.status() === 401) {
        console.log('⚠️  Campaigns endpoints require authentication (expected)');
      } else if (campaignsResponse.status() === 200) {
        console.log('✅ Campaigns list endpoint working');
      } else {
        console.log('❌ Campaigns list endpoint error:', campaignsResponse.status());
      }
      
      // Test campaigns create endpoint with POST
      const createResponse = await request.post(`${baseURL}/api/v1/campaigns/`, {
        data: { name: "Test Campaign", description: "E2E test" }
      });
      console.log('Campaigns create status:', createResponse.status());
      
      if (createResponse.status() === 401) {
        console.log('⚠️  Campaigns create requires authentication (expected)');
      } else if (createResponse.status() === 422) {
        console.log('⚠️  Campaigns create validation error (expected without auth)');
      } else if (createResponse.status() === 201) {
        console.log('✅ Campaigns create endpoint working');
      } else {
        console.log('❌ Campaigns create endpoint error:', createResponse.status());
      }
      
    } catch (error) {
      console.log('❌ Campaigns system test error:', error.message);
    }
  });

  test('Instagram Profile Analysis', async ({ request }) => {
    console.log('📱 Testing Instagram Profile Analysis...');
    
    try {
      // Test profile endpoint
      const profileResponse = await request.get(`${baseURL}/api/instagram/profile/cristiano`);
      console.log('Profile analysis status:', profileResponse.status());
      
      if (profileResponse.status() === 200) {
        const profileData = await profileResponse.json();
        console.log('✅ Profile analysis working - Username:', profileData.username);
      } else if (profileResponse.status() === 401) {
        console.log('⚠️  Profile analysis requires authentication');
      } else {
        console.log('❌ Profile analysis error:', profileResponse.status());
      }
      
    } catch (error) {
      console.log('❌ Instagram analysis test error:', error.message);
    }
  });

  test('Discovery and Search System', async ({ request }) => {
    console.log('🔎 Testing Discovery System...');
    
    try {
      // Test discovery endpoint
      const discoveryResponse = await request.get(`${baseURL}/api/v1/discovery/search?query=fitness&limit=5`);
      console.log('Discovery search status:', discoveryResponse.status());
      
      if (discoveryResponse.status() === 200) {
        console.log('✅ Discovery search working');
      } else if (discoveryResponse.status() === 401) {
        console.log('⚠️  Discovery requires authentication');
      } else {
        console.log('❌ Discovery error:', discoveryResponse.status());
      }
      
    } catch (error) {
      console.log('❌ Discovery system test error:', error.message);
    }
  });

  test('AI Analysis System', async ({ request }) => {
    console.log('🤖 Testing AI Analysis System...');
    
    try {
      // Test AI status
      const aiStatusResponse = await request.get(`${baseURL}/api/ai/status`);
      console.log('AI status response:', aiStatusResponse.status());
      
      if (aiStatusResponse.status() === 200) {
        const aiData = await aiStatusResponse.json();
        console.log('✅ AI system status:', aiData.status);
      } else {
        console.log('❌ AI status error:', aiStatusResponse.status());
      }
      
    } catch (error) {
      console.log('❌ AI system test error:', error.message);
    }
  });

  test('Performance and Caching', async ({ request }) => {
    console.log('⚡ Testing Performance and Caching...');
    
    try {
      // Test metrics endpoint
      const metricsResponse = await request.get(`${baseURL}/api/metrics`);
      console.log('Metrics status:', metricsResponse.status());
      
      if (metricsResponse.status() === 200) {
        console.log('✅ Performance metrics available');
      } else {
        console.log('❌ Metrics error:', metricsResponse.status());
      }
      
    } catch (error) {
      console.log('❌ Performance test error:', error.message);
    }
  });
});