# Feelcoin Community Faucet — foundation (NOT LIVE)

**Made by the Community, for the Community.**

A separate, deliberately payout-disabled faucet service designed for
https://faucet.feelcoin.org, matching the official gold/dark feelcoin.org identity.
Located under the website repository for review, but deployed independently.

## What is implemented
- Responsive landing page with existing official Feelcoin coin/favicon.
- Wallet choice: desktop alpha release (Windows/Linux) or web wallet; any valid
  FEEL public address should eventually be supported.
- Share-friendly /r/REFCODE links, Open Graph card, on-page copy/share actions.
- Persistent SQLite registration and referral records.
- Two-sided referral eligibility recorded as PENDING REVIEW; nothing paid.
- One registration per public address and originating IP per 24 hours.
- Cryptographically random referral IDs, rejection of self/same-IP referrals.
- Fail-closed Cloudflare Turnstile verification in pilot mode.
- A pure integer-atomic-units budget calculator (emission allowance, funding
  balance, daily cap); **not** wired to RPC and does not promise funds.
- Localhost-only demo mode and server-side feature flags.

## Node requirements

Node.js 22.13+ (built-in node:sqlite). Check if this runtime suits production
before release; run smoke and load tests on the target VPS. No npm dependencies.

## Start a safe localhost preview

    cd faucet
    FAUCET_DEMO_MODE=true npm start

Open http://127.0.0.1:8787. In this mode entries are simulated pending
registrations, not cryptocurrency claims. Database is stored in ./data/.
Stop the server when finished.

## Production registration-pilot configuration (not public money distribution)

    FAUCET_HOST=127.0.0.1
    PORT=8787
    FAUCET_PUBLIC_ORIGIN=https://faucet.feelcoin.org
    FAUCET_PILOT_ENABLED=true
    TURNSTILE_SITE_KEY=YOUR_PUBLIC_SITEKEY
    TURNSTILE_SECRET_KEY=YOUR_PRIVATE_SECRET
    FAUCET_IP_HASH_SECRET=LONG_RANDOM_PRIVATE_STRING
    FAUCET_DATA_DIR=/var/lib/feelcoin-faucet

All are environment variables, not values to commit to Git. Serve behind
a TLS reverse proxy. Restrict direct access, carefully configure actual
client-IP forwarding if needed (this prototype reads socket.remoteAddress
only and does not trust X-Forwarded-For). Do not use pilot mode behind
a shared proxy until trusted proxy IP handling is implemented.

## IMPORTANT: blockers before distributing real FEEL

1. Verify Feelcoin mainnet base58 address checksum/network prefix, including
   supported integrated/subaddresses. Current validation checks FORMAT only.
2. Connect node RPC to verified emission statistics (e.g. get_coinbase_tx_sum
   emission excluding transaction fees, with block times covering 24h);
   verify 12-decimal atomic-unit conversions and correct network.
3. Configure isolated, low-balance hot-wallet RPC bound to localhost,
   separate least-privilege payout worker, idempotent outgoing transfers,
   confirmation handling and reconciliation. Do not expose wallet RPC publicly.
4. Enforce daily allowance as min(emission fraction, remaining funded budget,
   explicit daily cap). Live payout switch MUST remain disabled until tested.
5. Add multi-node durable rate limiting and review measures for Sybil attacks,
   shared-IP users, proxy ingress, DoS, abuse and referral qualification.
6. Add opt-in public identity for any leaderboard, avoid linking a wallet
   address to someone's IP, identity or social profile without consent.
7. Security review, testnet/manual mainnet small-value tests, backups and
   monitoring before any live launch.

## Verify

    npm test

Do not claim that referral bonuses or faucet claims have been paid. The
current API returns pending_review with zero outgoing transfers by design.
No secrets, seeds, wallets or addresses should be committed to Git.
