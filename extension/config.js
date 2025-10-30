// AutoText Configuration
// Toggle between development and production by changing PRODUCTION flag

const CONFIG = {
  // Environment toggle - change this single value:
  PRODUCTION: false,  // ← CHANGE THIS: false = localhost, true = autotext.zua.ro

  // API URLs (automatically selected based on PRODUCTION flag)
  API_URL_DEV: 'http://localhost:8000/api',
  API_URL_PROD: 'https://autotext.zua.ro/api',

  // Development token (will be replaced with user-specific tokens in production)
  DEV_TOKEN: '4bedda61f31040c3776258bcd33b2a59ec51db06'
};

// Set API_URL based on environment
CONFIG.API_URL = CONFIG.PRODUCTION ? CONFIG.API_URL_PROD : CONFIG.API_URL_DEV;

console.log(`AutoText Config: ${CONFIG.PRODUCTION ? 'PRODUCTION' : 'DEVELOPMENT'} mode`);
console.log(`AutoText Config: Using API at ${CONFIG.API_URL}`);
