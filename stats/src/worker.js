import {
  MAX_OTP_ATTEMPTS,
  OTP_TTL_SECONDS,
  SESSION_TTL_SECONDS,
  clearCookie,
  equalHex,
  isSixDigitCode,
  otpDigest,
  parseCookies,
  randomDigits,
  randomToken,
  sameOrigin,
  secureCookie,
  sha256,
  validEmail,
} from "./core.js";

const JSON_HEADERS = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
};

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...JSON_HEADERS, ...headers },
  });
}

function securityHeaders(response) {
  const headers = new Headers(response.headers);
  headers.set("Cache-Control", "no-store");
  headers.set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
  headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()");
  headers.set("Referrer-Policy", "no-referrer");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

function requestIp(request) {
  return request.headers.get("CF-Connecting-IP") || "local";
}

async function sessionRecord(request, env) {
  const token = parseCookies(request.headers.get("Cookie")).stats_session;
  if (!token) return null;
  return env.AUTH.get(`session:${await sha256(token)}`, "json");
}

async function requireSession(request, env) {
  const session = await sessionRecord(request, env);
  return session ? null : json({ error: "Authentication required" }, 401);
}

async function sendAccessCode(env, email, code, challengeId) {
  const apiKey = String(env.RESEND_API_KEY || "");
  const fromEmail = String(env.RESEND_FROM_EMAIL || "");
  if (!apiKey.startsWith("re_") || !validEmail(fromEmail)) {
    throw new Error("Resend is not configured");
  }

  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      "Idempotency-Key": `yudy-stats-${challengeId}`,
    },
    body: JSON.stringify({
      from: `YUDY <${fromEmail}>`,
      to: [email],
      subject: "Your YUDY access code",
      html: `
        <div style="background:#07111f;color:#f5f8ff;font-family:Arial,sans-serif;padding:40px 16px">
          <div style="background:#0d1a2c;border:1px solid #203553;border-radius:20px;margin:auto;max-width:416px;padding:32px">
            <p style="color:#65d6ff;font-size:14px;font-weight:700;letter-spacing:2px;margin:0 0 20px">YUDY // STATS</p>
            <h1 style="font-size:26px;line-height:1.25;margin:0 0 12px">Your access code</h1>
            <p style="color:#a9b8cd;font-size:15px;line-height:1.6;margin:0 0 24px">Enter this one-time code on the YUDY stats page:</p>
            <p style="background:#081423;border-radius:14px;color:#fff;font-size:34px;font-weight:700;letter-spacing:9px;margin:0 0 24px;padding:18px;text-align:center">${code}</p>
            <p style="color:#71829a;font-size:13px;line-height:1.5;margin:0">If you did not request this code, you can ignore this email.</p>
          </div>
        </div>
      `,
    }),
  });
  if (!response.ok) throw new Error(`Resend request failed with status ${response.status}`);
}

async function requestCode(request, env) {
  if (!sameOrigin(request)) return json({ error: "Invalid request origin" }, 403);
  if (await sessionRecord(request, env)) return json({ authenticated: true });

  const adminEmail = String(env.ADMIN_EMAIL || "");
  if (!validEmail(adminEmail)) {
    return json({ error: "Authentication service is not configured" }, 503);
  }

  const ipHash = await sha256(requestIp(request));
  const rateKey = `otp-rate:${ipHash}`;
  if (await env.AUTH.get(rateKey)) {
    return json({ error: "A code was sent recently", retryAfter: 60 }, 429, { "Retry-After": "60" });
  }

  const challengeId = randomToken();
  const code = randomDigits();
  const record = {
    digest: await otpDigest(challengeId, code),
    attempts: 0,
    createdAt: new Date().toISOString(),
  };

  await env.AUTH.put(rateKey, "1", { expirationTtl: 60 });
  await env.AUTH.put(`otp:${challengeId}`, JSON.stringify(record), { expirationTtl: OTP_TTL_SECONDS });

  try {
    await sendAccessCode(env, adminEmail, code, challengeId);
  } catch (error) {
    await Promise.all([env.AUTH.delete(rateKey), env.AUTH.delete(`otp:${challengeId}`)]);
    console.error("Stats access email failed", error);
    return json({ error: "Could not send an access code" }, 503);
  }

  const headers = new Headers(JSON_HEADERS);
  headers.append("Set-Cookie", secureCookie("stats_challenge", challengeId, OTP_TTL_SECONDS));
  return new Response(JSON.stringify({ ok: true, expiresIn: OTP_TTL_SECONDS }), { status: 200, headers });
}

async function verifyCode(request, env) {
  if (!sameOrigin(request)) return json({ error: "Invalid request origin" }, 403);
  const challengeId = parseCookies(request.headers.get("Cookie")).stats_challenge;
  const payload = await request.json().catch(() => ({}));
  const code = String(payload.code || "");
  if (!challengeId || !isSixDigitCode(code)) return json({ error: "Enter the six-digit code" }, 400);

  const key = `otp:${challengeId}`;
  const record = await env.AUTH.get(key, "json");
  if (!record) return json({ error: "The code expired. Request a new one." }, 401);
  if (record.attempts >= MAX_OTP_ATTEMPTS) {
    await env.AUTH.delete(key);
    return json({ error: "Too many attempts. Request a new code." }, 429);
  }

  const verified = equalHex(record.digest || "", await otpDigest(challengeId, code));
  if (!verified) {
    record.attempts += 1;
    await env.AUTH.put(key, JSON.stringify(record), { expirationTtl: OTP_TTL_SECONDS });
    return json({ error: "Incorrect code", attemptsRemaining: MAX_OTP_ATTEMPTS - record.attempts }, 401);
  }

  const sessionToken = randomToken();
  await Promise.all([
    env.AUTH.delete(key),
    env.AUTH.put(`session:${await sha256(sessionToken)}`, JSON.stringify({ createdAt: new Date().toISOString() }), { expirationTtl: SESSION_TTL_SECONDS }),
  ]);

  const headers = new Headers(JSON_HEADERS);
  headers.append("Set-Cookie", clearCookie("stats_challenge"));
  headers.append("Set-Cookie", secureCookie("stats_session", sessionToken, SESSION_TTL_SECONDS));
  return new Response(JSON.stringify({ ok: true }), { status: 200, headers });
}

async function logout(request, env) {
  if (!sameOrigin(request)) return json({ error: "Invalid request origin" }, 403);
  const token = parseCookies(request.headers.get("Cookie")).stats_session;
  if (token) await env.AUTH.delete(`session:${await sha256(token)}`);
  return json({ ok: true }, 200, { "Set-Cookie": clearCookie("stats_session") });
}

async function loadStats(env) {
  const totalsQuery = env.DB.prepare(`
    SELECT
      (SELECT COUNT(*) FROM users WHERE is_active = 1) AS registered_accounts,
      (SELECT COUNT(*) FROM analytics_events WHERE event_name = 'ai_xstocks_selection_generated') AS ai_requests,
      (SELECT COALESCE(SUM(CAST(json_extract(properties, '$.count') AS INTEGER)), 0)
         FROM analytics_events WHERE event_name = 'ai_xstocks_selection_generated') AS processed_assets
  `);
  const seriesQuery = env.DB.prepare(`
    WITH RECURSIVE dates(day) AS (
      SELECT date('now', '-29 days')
      UNION ALL
      SELECT date(day, '+1 day') FROM dates WHERE day < date('now')
    )
    SELECT
      dates.day,
      (SELECT COUNT(*) FROM users u
        WHERE u.is_active = 1 AND substr(u.created_at, 1, 10) = dates.day) AS accounts,
      (SELECT COUNT(*) FROM analytics_events e
        WHERE e.event_name = 'ai_xstocks_selection_generated'
          AND substr(e.created_at, 1, 10) = dates.day) AS ai_requests,
      (SELECT COALESCE(SUM(CAST(json_extract(e.properties, '$.count') AS INTEGER)), 0)
        FROM analytics_events e
        WHERE e.event_name = 'ai_xstocks_selection_generated'
          AND substr(e.created_at, 1, 10) = dates.day) AS processed_assets
    FROM dates ORDER BY dates.day
  `);
  const [totals, series] = await Promise.all([totalsQuery.first(), seriesQuery.all()]);
  return {
    totals: {
      registeredAccounts: Number(totals?.registered_accounts || 0),
      aiRequests: Number(totals?.ai_requests || 0),
      processedAssets: Number(totals?.processed_assets || 0),
    },
    series: (series.results || []).map((row) => ({
      day: row.day,
      accounts: Number(row.accounts || 0),
      aiRequests: Number(row.ai_requests || 0),
      processedAssets: Number(row.processed_assets || 0),
    })),
    updatedAt: new Date().toISOString(),
  };
}

async function handleApi(request, env) {
  const url = new URL(request.url);
  if (request.method === "POST" && url.pathname === "/api/auth/request") return requestCode(request, env);
  if (request.method === "POST" && url.pathname === "/api/auth/verify") return verifyCode(request, env);
  if (request.method === "POST" && url.pathname === "/api/auth/logout") return logout(request, env);
  if (request.method === "GET" && url.pathname === "/api/stats") {
    const denied = await requireSession(request, env);
    return denied || json(await loadStats(env));
  }
  return json({ error: "Not found" }, 404);
}

export default {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);
      const response = url.pathname.startsWith("/api/")
        ? await handleApi(request, env)
        : await env.ASSETS.fetch(request);
      return securityHeaders(response);
    } catch (error) {
      console.error("Stats worker error", error);
      return securityHeaders(json({ error: "Unexpected server error" }, 500));
    }
  },
};
