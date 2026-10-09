export const OTP_TTL_SECONDS = 10 * 60;
export const SESSION_TTL_SECONDS = 12 * 60 * 60;
export const MAX_OTP_ATTEMPTS = 5;

export function parseCookies(header = "") {
  return Object.fromEntries(
    String(header || "")
      .split(";")
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => {
        const index = part.indexOf("=");
        return index === -1
          ? [part, ""]
          : [part.slice(0, index), decodeURIComponent(part.slice(index + 1))];
      }),
  );
}

export function secureCookie(name, value, maxAge) {
  return `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Strict`;
}

export function clearCookie(name) {
  return `${name}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict`;
}

export function randomDigits(random = crypto.getRandomValues.bind(crypto)) {
  const values = new Uint32Array(1);
  random(values);
  return String(values[0] % 1_000_000).padStart(6, "0");
}

export function randomToken(random = crypto.getRandomValues.bind(crypto)) {
  const bytes = new Uint8Array(32);
  random(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function sha256(value) {
  const encoded = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function otpDigest(challengeId, code) {
  return sha256(`${challengeId}:${code}`);
}

export function equalHex(left, right) {
  if (left.length !== right.length) return false;
  let mismatch = 0;
  for (let index = 0; index < left.length; index += 1) {
    mismatch |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return mismatch === 0;
}

export function isSixDigitCode(value) {
  return /^\d{6}$/.test(String(value ?? ""));
}

export function sameOrigin(request, expectedHost = "stats.yudyai.xyz") {
  const origin = request.headers.get("Origin");
  return origin === `https://${expectedHost}` || origin === "http://localhost:8787";
}

export function validEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) && !/[\r\n]/.test(value);
}
