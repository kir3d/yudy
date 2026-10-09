import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  clearCookie,
  equalHex,
  isSixDigitCode,
  otpDigest,
  parseCookies,
  randomDigits,
  secureCookie,
  validEmail,
} from "../src/core.js";

test("cookie helpers preserve secure authentication attributes", () => {
  const cookie = secureCookie("stats_session", "a b", 60);
  assert.match(cookie, /^stats_session=a%20b;/);
  assert.match(cookie, /HttpOnly/);
  assert.match(cookie, /Secure/);
  assert.match(cookie, /SameSite=Strict/);
  assert.deepEqual(parseCookies("one=1; stats_session=a%20b"), { one: "1", stats_session: "a b" });
  assert.deepEqual(parseCookies(null), {});
  assert.match(clearCookie("stats_session"), /Max-Age=0/);
});

test("OTP validation accepts exactly six digits", () => {
  assert.equal(isSixDigitCode("012345"), true);
  assert.equal(isSixDigitCode("12345"), false);
  assert.equal(isSixDigitCode("12345a"), false);
});

test("OTP generation and challenge-bound digest verification", async () => {
  assert.equal(randomDigits((values) => { values[0] = 7; }), "000007");
  assert.equal(randomDigits((values) => { values[0] = 1_234_567; }), "234567");

  const digest = await otpDigest("challenge-a", "123456");
  assert.equal(equalHex(digest, await otpDigest("challenge-a", "123456")), true);
  assert.equal(equalHex(digest, await otpDigest("challenge-b", "123456")), false);
  assert.equal(equalHex(digest, await otpDigest("challenge-a", "654321")), false);
});

test("email validation rejects header injection", () => {
  assert.equal(validEmail("admin@example.com"), true);
  assert.equal(validEmail("admin@example.com\nBcc: attacker@example.com"), false);
});

test("public files never reveal the private destination address", async () => {
  const files = await Promise.all([
    readFile(new URL("../public/index.html", import.meta.url), "utf8"),
    readFile(new URL("../public/app.js", import.meta.url), "utf8"),
  ]);
  assert.equal(/[A-Z0-9._%+-]+@gmail\.com/i.test(files.join("\n")), false);
});
