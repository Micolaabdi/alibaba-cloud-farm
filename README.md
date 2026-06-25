# Alibaba Cloud Account Farm

Bulk-register Alibaba Cloud accounts and harvest Model Studio API keys. Each new account gets **1M free tokens** for Qwen models.

## Features

- **Camoufox browser automation** (Firefox-based, anti-detect)
- **IMAP OTP verification** — Cloudflare catch-all domain → Gmail
- **No login needed** — session carries from register to Model Studio
- **Auto slider skip** — if Baxia captcha appears, skip and retry
- **API key extraction** — `sk-ws-...` key auto-extracted from modal

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

## Setup

```bash
pip install -r requirements.txt
camoufox fetch  # download browser binary (~700MB)
sudo chmod 666 /dev/uinput  # for slider solver (optional)
```

## Config

Edit `farm.py`:
```python
GMAIL_USER = "your@gmail.com"
GMAIL_APP_PW = "your app password"
EMAIL_DOMAIN = "yourdomain.com"  # Cloudflare catch-all → Gmail
```

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
curl https://ws-xxxxx.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer sk-ws-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.7-max","messages":[{"role":"user","content":"Hello"}]}'
```
