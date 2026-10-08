// Dynamic API routing based on environment
let apiBase = 'https://zazc8i568e.execute-api.us-east-1.amazonaws.com/prod';

// Use Staging API for localhost development and the staging S3 bucket
if (window.location.hostname === 'localhost' || 
    window.location.hostname === '127.0.0.1' || 
    window.location.hostname.includes('staging')) {
    apiBase = 'https://5h9f59awah.execute-api.us-east-1.amazonaws.com/staging';
}

export const API_BASE = apiBase;
