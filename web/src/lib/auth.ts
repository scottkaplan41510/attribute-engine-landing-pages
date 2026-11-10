export const COOKIE = "waf_access";

/** The cookie holds a hash of the passcode, never the passcode. */
export async function accessToken(passcode: string) {
  const bytes = new TextEncoder().encode(`website-attribute-finder:${passcode}`);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}
