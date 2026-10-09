<p align="center">
  <img src="image.jpg" alt="YUDY logo" width="340">
</p>

<h1 align="center">YUDY</h1>

<p align="center"><strong>Personalized discovery for tokenized stocks and ETFs.</strong></p>

<p align="center">
  <a href="https://yudyai.xyz">Website</a> ·
  <a href="https://docs.google.com/presentation/d/1dOIxFOu7D53IkXsvg90zh15tEy1T1EB16-fw1pU4IY4/edit?usp=sharing">Pitch deck</a> ·
  <a href="https://api.yudyai.xyz/health">API status</a>
</p>

<p align="center">
  <img alt="Android" src="https://img.shields.io/badge/Android-Kotlin-3DDC84?logo=android&logoColor=white">
  <img alt="Cloudflare Workers" src="https://img.shields.io/badge/Backend-Cloudflare_Workers-F38020?logo=cloudflare&logoColor=white">
  <img alt="Solana" src="https://img.shields.io/badge/Ecosystem-Solana-9945FF?logo=solana&logoColor=white">
  <img alt="Status" src="https://img.shields.io/badge/status-MVP-59D9FF">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-59D9FF">
</p>

> YUDY does not tell people what to buy. It helps them discover what to explore.

## The problem

Tokenized stocks and ETFs are spread across venues, data providers, and analytics products. Investors can find market data, but turning it into a focused list that reflects their interests and risk context still takes time and specialist knowledge.

Most products begin with the market. YUDY begins with the person.

## The solution

YUDY is a mobile discovery assistant for real xStocks. It combines a user's risk profile, interests, regions, and previous reactions with live asset data to produce a focused **For You** feed.

The product keeps discovery separate from execution. Users can inspect an asset, like it, dismiss it, save it, or open an external CEX or DEX where it is available. YUDY never handles funds or executes a transaction.

## How it works

1. **Create a profile**  
   Complete onboarding, describe investment context, and receive an investor profile.

2. **Explore a focused xStocks selection**  
   YUDY evaluates real assets using the profile, market data, and interaction history. The AI receives an allowlisted profile context without the user's email, name, credentials, or authentication tokens.

3. **Shape future discovery**  
   Like, dismiss, or save assets. Dismissed assets leave **For You** while remaining available in **Discover**. **Buy** opens an external provider.

## Why now

- Kazakhstan introduced a comprehensive digital-asset framework on **May 1, 2026**, including rules for tokenized real assets and digital forms of traditional financial instruments. [National Bank of Kazakhstan](https://nationalbank.kz/en/news/informacionnye-soobshcheniya/19193)
- On **September 17, 2026**, the U.S. SEC issued limited, conditional relief intended to facilitate permissioned onchain trading of tokenized NMS stocks through eligible venues. [U.S. Securities and Exchange Commission](https://www.sec.gov/newsroom/press-releases/2026-90-sec-issues-innovation-exemption-facilitate-trading-tokenized-nms-stock-request-comment)
- The xStocks ecosystem provides a growing set of tokenized equities and ETFs that can be discovered through a single product experience.

## Why Solana

YUDY focuses on the Solana xStocks ecosystem because it combines fast settlement infrastructure, low transaction costs, and active tokenized-asset venues. Those properties support frequent market updates and make external exploration practical for mobile users.

YUDY is an information layer over this ecosystem. It does not submit trades to Solana or any other network.

## MVP features

- Email registration and sign-in through Supabase Auth
- Encrypted Android session storage and automatic sign-in
- Versioned legal documents with one-action acceptance for new accounts
- Investor onboarding and risk-profile assessment
- AI-assisted xStocks selection using anonymous, allowlisted context
- Real xStocks catalog with logos, quotes, and seven-day price charts
- **For You**, **Discover**, **Saved**, and **Learn** sections
- Like, dislike, and save feedback that affects future selections
- Full asset pages with underlying and tokenized-asset information
- External CEX and DEX links for assets with known venues
- Profile settings, sign-out, and account deletion
- Private operational dashboard for account, AI-request, and processed-asset statistics

## Product positioning

| Category | Typical strength | Discovery gap |
| --- | --- | --- |
| Broad market products such as Investing.com and CoinMarketCap | Large catalogs, quotes, and news | Discovery is usually generic |
| RWA and DeFi analytics such as RWA.xyz and DeFiLlama | Protocol and token analytics | The experience begins with data, not user context |
| **YUDY** | Profile-aware xStocks discovery | Focused MVP catalog and early-stage product |

## Technology

| Layer | Technology |
| --- | --- |
| Android | Kotlin, Jetpack Compose, Material 3, Hilt, Retrofit, Moshi, Room, DataStore, Coroutines, StateFlow |
| Production API | Python, FastAPI-compatible ASGI application, Cloudflare Workers, pywrangler |
| Authentication | Supabase Auth |
| Production data | Cloudflare D1 |
| Personalization | Rule-based ranking plus Cloudflare Workers AI |
| Market data | xStocks API and CoinGecko |
| Local reference backend | FastAPI, PostgreSQL, Redis, SQLAlchemy, Alembic |
| Delivery | Wrangler, Docker Compose, Gradle |

## Architecture

```text
┌─────────────────────┐       HTTPS       ┌──────────────────────────┐
│ Android application │ ─────────────────▶│ Cloudflare Worker API    │
│ Compose + MVVM       │                   │ Python + ASGI            │
└──────────┬──────────┘                   └────────────┬─────────────┘
           │                                           │
           │ local cache                               ├── Supabase Auth
           ▼                                           ├── Cloudflare D1
┌─────────────────────┐                                ├── Workers AI
│ Room + DataStore    │                                ├── xStocks API
└─────────────────────┘                                └── CoinGecko

Asset page ── Buy ──▶ external CEX or DEX
```

The API builds an explicit AI payload from risk level, interests, regions, and interaction signals. Identity and authentication fields are excluded before the request reaches the model. The response is validated against the current asset catalog before it is shown in the app.

## Planned business model

Subscriptions are part of the product plan and are not enabled in the current MVP.

| Plan | Planned price | Planned focus |
| --- | ---: | --- |
| Free | $0 | Basic discovery and personalization, supported by ads |
| Discover | $5.99/month | Expanded discovery and basic research |
| Research | $11.99/month | Full discovery, advanced AI, and deeper research |
| Private | $24.99/month | Premium AI, advanced research, and maximum personalization |

Short access passes for 12, 24, and 48 hours are also under consideration.

## Repository

```text
.
├── android/          # Native Android application
├── backend/          # Docker-based FastAPI reference backend
├── landing/          # Public website for yudyai.xyz
├── stats/            # Private operational dashboard Worker
├── worker-backend/   # Production Cloudflare Worker API
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick start

### Android

Requirements: JDK 17 and Android SDK 36.

```bash
cd android
./gradlew testDebugUnitTest lintDebug assembleDebug
```

The debug build uses `https://api.yudyai.xyz/` by default. Override `YUDY_API_URL` through a Gradle property when testing another backend. Release builds use `YUDY_RELEASE_API_URL`.

### Docker backend

The Docker environment runs PostgreSQL, Redis, the FastAPI backend, and the demo market-data provider.

```bash
cp .env.example .env
# Set a strong JWT_SECRET in .env
docker compose up --build
```

The local API is available at `http://localhost:8000`.

### Cloudflare Worker backend

Requirements: Node.js, npm, a Cloudflare account, and the required Supabase and Cloudflare configuration.

```bash
cd worker-backend
npm install
cp wrangler.jsonc.example wrangler.jsonc
cp .dev.vars.example .dev.vars
npm run dev
```

Keep `.dev.vars`, `.env`, Wrangler state, keystores, and signing credentials out of version control.

## Roadmap

### Built

- Native Android discovery flow
- Risk and investor profiles
- Personalized and full-catalog xStocks feeds
- Interaction-aware ranking and cached selections
- Asset pages, charts, venue links, and external redirects
- Cloudflare production backend and private operational analytics

### Next 6 to 12 months

- Publish a signed Android release
- Complete independent security and legal reviews
- Expand market coverage and venue metadata
- Validate subscriptions, research tools, and short-term passes
- Grow community and distribution partnerships
- Develop the next YUDY Intelligence research experience

The current pitch deck identifies a **$650K funding requirement** for product, engineering, security, legal, growth, and community work. The investment structure remains to be defined.

## Team

| Name | Role | Background |
| --- | --- | --- |
| **Yuliya Salyuleva** | CEO | 20+ years in investment and finance, international consulting, cross-border projects, and business development |
| **Kirill Mukha** | CTO | 16+ years in mobile development and 5+ years building onchain analytics tools |

## Resources

- [YUDY website](https://yudyai.xyz)
- [Pitch deck](https://docs.google.com/presentation/d/1dOIxFOu7D53IkXsvg90zh15tEy1T1EB16-fw1pU4IY4/edit?usp=sharing)
- [Production API health](https://api.yudyai.xyz/health)
- [xStocks DeFi ecosystem](https://defi.xstocks.fi/)
- [xStocks analytics on Dune](https://dune.com/xstocks/xstocks)

## Security and privacy

- Secrets are supplied through environment variables or platform secret stores.
- The mobile app stores session material in encrypted local storage.
- AI selection requests exclude direct identity and authentication data.
- Legal acceptance records include document versions and acceptance timestamps.
- Account deletion is available from the profile screen.

Please report a suspected vulnerability privately to the project maintainers rather than opening a public issue.

## Disclaimer

YUDY is an information and discovery product. It is not a broker, investment adviser, custodian, exchange, execution venue, or payment processor. YUDY does not hold user funds, execute transactions, or guarantee returns. Asset information may be delayed or incomplete. Users must conduct their own research and review the terms and risks of any external provider before taking action.

## License

This project is available under the [MIT License](LICENSE).
