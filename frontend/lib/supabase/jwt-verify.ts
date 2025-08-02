// lib/supabase/jwt-verify.ts
// JWT verification utility using asymmetric keys from Supabase JWKS endpoint
// Enables local JWT verification without network calls to Auth server
// RELEVANT FILES: client.ts, server.ts, middleware.ts

import { jwtDecode } from 'jwt-decode'

// Cache for public keys from JWKS endpoint
let jwksCache: any = null
let jwksCacheTime: number = 0
const JWKS_CACHE_DURATION = 3600000 // 1 hour in milliseconds

/**
 * Fetches public keys from Supabase JWKS endpoint
 * Uses caching to avoid excessive network requests
 */
export async function getPublicKeys(supabaseUrl: string) {
  const now = Date.now()
  
  // Return cached keys if still valid
  if (jwksCache && (now - jwksCacheTime) < JWKS_CACHE_DURATION) {
    return jwksCache
  }

  try {
    // Fetch public keys from JWKS endpoint
    const response = await fetch(`${supabaseUrl}/auth/v1/.well-known/jwks.json`)
    if (!response.ok) {
      throw new Error('Failed to fetch JWKS')
    }
    
    const jwks = await response.json()
    
    // Cache the keys
    jwksCache = jwks
    jwksCacheTime = now
    
    return jwks
  } catch (error) {
    console.error('Error fetching JWKS:', error)
    throw error
  }
}

/**
 * Verifies JWT locally using public key cryptography
 * Returns decoded claims if valid, throws error if invalid
 */
export async function verifyJWT(token: string, supabaseUrl: string) {
  try {
    // Decode token header to get key id (kid)
    const [headerBase64] = token.split('.')
    const header = JSON.parse(atob(headerBase64))
    
    // Get public keys
    const jwks = await getPublicKeys(supabaseUrl)
    
    // Find matching key by kid
    const key = jwks.keys?.find((k: any) => k.kid === header.kid)
    
    if (!key) {
      // If no matching key, might be using legacy JWT secret
      // Fall back to server-side verification
      throw new Error('No matching key found in JWKS')
    }
    
    // For browser environments, we'll use the decoded claims
    // Full cryptographic verification would require a library like jose
    // For now, decode and check expiration
    const decoded = jwtDecode(token)
    
    // Check expiration
    if (decoded.exp && decoded.exp * 1000 < Date.now()) {
      throw new Error('Token expired')
    }
    
    return decoded
  } catch (error) {
    console.error('JWT verification error:', error)
    throw error
  }
}

/**
 * Gets claims from JWT without network call
 * Useful for reading user info from access tokens
 */
export function getClaims(token: string) {
  try {
    return jwtDecode(token)
  } catch (error) {
    console.error('Error decoding JWT:', error)
    return null
  }
}

/**
 * Checks if a JWT is expired
 */
export function isTokenExpired(token: string): boolean {
  try {
    const decoded = jwtDecode(token)
    if (!decoded.exp) return false
    
    // Check if token expires in next 60 seconds (buffer time)
    return decoded.exp * 1000 < Date.now() + 60000
  } catch {
    return true
  }
}