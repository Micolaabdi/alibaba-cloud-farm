# Alibaba Cloud Account Farm

Bulk-register Alibaba Cloud accounts and harvest Model Studio API keys. Each new account gets **1M free tokens** for Qwen models.

## Features

- **Camoufox browser automation** (Firefox-based, anti-detect)
- **IMAP OTP verification** — works with any IMAP provider (Gmail, Outlook, etc.)
- **No login needed** — session carries from register to Model Studio
- **Auto slider skip** — if Baxia captcha appears, skip and retry
- **API key extraction** — `sk-ws-...` key auto-extracted from modal
- **Configurable via `.env`** — no hardcoded credentials

## Flow (9 steps)

1. Navigate to Alibaba Cloud register page
2. Select Individual account → Next
3. Fill email + password → Sign Up (Step 1)
4. Select Email verification tab
5. Set country = Singapore → Send OTP
6. Read OTP from IMAP → type → Sign Up (Step 2)
7. Open Model Studio (no login — session carries from register)
8. Dashboard → API Key → Create API Key → OK
9. Extract `sk-ws-...` API key from modal

## Prerequisites

### 1. Catch-all Domain

You need a domain with **catch-all email forwarding** — any `*@yourdomain.com` lands in your inbox.

Options:
- **Cloudflare Email Routing** (free) — set catch-all rule → forward to your Gmail
- **ImprovMX** (free tier) — MX records → forward to your email
- **Self-hosted** — any mail server with catch-all alias

### 2. Gmail App Password

If using Gmail as your inbox:

1. Enable **2-Step Verification**: [Google Account → Security](https://myaccount.google.com/security)
2. Generate **App Password**: [Google Account → App passwords](https://myaccount.google.com/apppasswords)
3. Copy the 16-char password (format: `abcd efgh ijkl mnop`)

## Setup

```bash
git clone https://github.com/Micolaabdi/alibaba-cloud-farm.git
cd alibaba-cloud-farm

pip install -r requirements.txt
camoufox fetch  # download browser binary (~700MB)
sudo chmod 666 /dev/uinput  # for slider solver (optional)
```

## Config

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
IMAP_USER=your@gmail.com
IMAP_PASS=abcd efgh ijkl mnop
EMAIL_DOMAIN=your-catchall-domain.com
```

Or export as environment variables:

```bash
export IMAP_USER="your@gmail.com"
export IMAP_PASS="abcd efgh ijkl mnop"
export EMAIL_DOMAIN="yourdomain.com"
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `IMAP_USER` | ✅ | — | Your IMAP email address (e.g. Gmail) |
| `IMAP_PASS` | ✅ | — | IMAP password (Gmail App Password, not your regular password) |
| `EMAIL_DOMAIN` | ✅ | — | Your catch-all domain for receiving OTPs |
| `IMAP_HOST` | ❌ | `imap.gmail.com` | IMAP server hostname |
| `IMAP_PORT` | ❌ | `993` | IMAP server port |
| `RESULTS_FILE` | ❌ | `results.json` | Path to save harvested accounts |

## Run

```bash
xvfb-run -a python3 farm.py
```

## Results

Accounts saved to `results.json`:

```json
[
  {
    "email": "abc123@yourdomain.com",
    "password": "Aa1xxxxxxxxxxxx",
    "api_key": "sk-ws-H.LIDDEM...",
    "timestamp": "2026-06-26 00:47:12"
  }
]
```

## Notes

- **Slider captcha** appears ~50% on datacenter IPs. Script skips and retries.
- **OTP** is unique per email. Regex extracts from `<span>` tag, NOT CSS color codes.
- **No proxy needed** — direct VPS IP works (slider skip handles it).
- **1M free tokens** per account for Qwen3.7-Max, Qwen3.7-Plus, etc.

## API Key Usage

```bash
curl https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.7-max","messages":[{"role":"user","content":"Hello"}]}'
```
