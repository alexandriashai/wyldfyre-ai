/**
 * Wyld Fyre AI - Authentication Utilities
 *
 * Handles token storage and retrieval for authentication.
 */

const TOKEN_KEY = 'wyld_fyre_token';
const REFRESH_TOKEN_KEY = 'wyld_fyre_refresh_token';

/**
 * Check if running in browser environment
 */
function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

/**
 * Store the access token
 */
export function setToken(token: string): void {
  if (isBrowser()) {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

/**
 * Retrieve the access token
 */
export function getToken(): string | null {
  if (isBrowser()) {
    return localStorage.getItem(TOKEN_KEY);
  }
  return null;
}

/**
 * Remove the access token
 */
export function removeToken(): void {
  if (isBrowser()) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
}

/**
 * Store the refresh token
 */
export function setRefreshToken(token: string): void {
  if (isBrowser()) {
    localStorage.setItem(REFRESH_TOKEN_KEY, token);
  }
}

/**
 * Retrieve the refresh token
 */
export function getRefreshToken(): string | null {
  if (isBrowser()) {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }
  return null;
}

/**
 * Check if user is authenticated (has a token)
 */
export function isAuthenticated(): boolean {
  return !!getToken();
}

/**
 * Parse JWT token payload (without verification)
 * Only use for display purposes, server should validate
 */
export function parseToken(token: string): {
  sub: string;
  email: string;
  username: string;
  is_admin: boolean;
  exp: number;
  iat: number;
} | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;

    const payload = JSON.parse(atob(parts[1]));
    return payload;
  } catch {
    return null;
  }
}

/**
 * Check if token is expired
 */
export function isTokenExpired(token: string): boolean {
  const payload = parseToken(token);
  if (!payload) return true;

  // Add 60 second buffer for clock skew
  const expirationTime = payload.exp * 1000;
  return Date.now() > expirationTime - 60000;
}

/**
 * Get time until token expiration in seconds
 */
export function getTokenExpiresIn(token: string): number {
  const payload = parseToken(token);
  if (!payload) return 0;

  const expirationTime = payload.exp * 1000;
  const remainingMs = expirationTime - Date.now();
  return Math.max(0, Math.floor(remainingMs / 1000));
}
