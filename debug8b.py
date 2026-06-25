#!/usr/bin/env python3
"""Debug step 8-9 only — test API key creation on Model Studio.
Uses fresh Camoufox session, navigates directly to API key page.
We need to login first with existing account, then go to API key page.
"""

import time
import re
import json
from camoufox.sync_api import Camoufox

# Use the last registered account
EMAIL = None  # Will read from result.json if available
PASSWORD = None

# Try to read last registered account
try:
    with open("/home/ubuntu/alibaba-farm/result.json") as f:
        data = json.load(f)
        EMAIL = data.get("email")
        PASSWORD = data.get("password")
    print(f"Using account: {EMAIL}")
except:
    print("No previous account found. Will try direct navigation (maybe session still valid)")

LOGIN_URL = "https://signin.alibabacloud.com/login.htm"
APIKEY_URL = "https://modelstudio.console.alibabacloud.com/ap-southeast-1?tab=api"

with Camoufox(headless=False, geoip=True, humanize=True, locale="en-US") as browser:
    page = browser.new_page()

    # Step 1: Login first
    if EMAIL and PASSWORD:
        print(f"[1] Logging in as {EMAIL}...")
        page.goto(LOGIN_URL, timeout=120000, wait_until="domcontentloaded")
        time.sleep(5)
        page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8_login.png")

        # Find login form (might be in iframe too)
        frame = None
        for f in page.frames[1:]:
            if "passport" in f.url or "signin" in f.url:
                frame = f
                break
        if not frame:
            frame = page  # Try main page

        # Fill email
        email_input = frame.query_selector("input[type='email']") or \
                      frame.query_selector("input[name='email']") or \
                      frame.query_selector("input[placeholder*='email']") or \
                      frame.query_selector("input#username")
        if email_input:
            email_input.fill(EMAIL)
            print(f"[1] Filled email")

        # Fill password
        pw_input = frame.query_selector("input[type='password']") or \
                   frame.query_selector("input[name='password']")
        if pw_input:
            pw_input.fill(PASSWORD)
            print(f"[1] Filled password")

        # Click Sign In
        for b in frame.query_selector_all("button, [role='button'], input[type='submit']"):
            txt = b.inner_text().lower() if b.inner_text() else ""
            val = (b.get_attribute("value") or "").lower()
            if "sign in" in txt or "login" in txt or "sign in" in val:
                b.click()
                print(f"[1] Clicked Sign In")
                break

        time.sleep(10)
        page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8_after_login.png")
        print(f"[1] Current URL: {page.url}")

    # Step 2: Navigate to API Key page
    print(f"\n[2] Navigating to API Key page...")
    page.goto(APIKEY_URL, timeout=120000, wait_until="domcontentloaded")
    time.sleep(15)
    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8_apikey_page.png")
    print(f"[2] Current URL: {page.url}")

    # Print body text
    body = page.inner_text("body")[:3000]
    print(f"[2] Body text:\n{body}")

    # List all buttons
    print(f"\n[3] All visible buttons:")
    btns = page.query_selector_all("button, [role='button'], a")
    for b in btns:
        try:
            txt = b.inner_text()[:100]
            vis = b.is_visible()
            if vis and txt.strip():
                print(f"  BTN: '{txt}' visible={vis}")
        except:
            pass

    # Check frames
    print(f"\n[4] Frames: {len(page.frames)}")
    for i, f in enumerate(page.frames):
        print(f"  frame[{i}]: {f.url[:150]}")

    # Look for "Create" button specifically
    print(f"\n[5] Looking for Create buttons...")
    for b in btns:
        try:
            txt = b.inner_text()[:100].lower()
            if "create" in txt and b.is_visible():
                print(f"  FOUND: '{b.inner_text()[:100]}' — clicking!")
                b.click()
                time.sleep(3)
                page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8_create_clicked.png")
                break
        except:
            pass

    # Check for modal after clicking create
    print(f"\n[6] Checking for modal after create click...")
    time.sleep(3)
    modals = page.query_selector_all("[class*='modal'], [role='dialog']")
    for m in modals:
        if m.is_visible():
            print(f"  Modal visible: {m.get_attribute('class')[:80]}")
            modal_text = m.inner_text()[:500]
            print(f"  Modal text: {modal_text}")

            # Look for create/confirm button in modal
            modal_btns = m.query_selector_all("button, [role='button']")
            for mb in modal_btns:
                txt = mb.inner_text()[:80].lower()
                print(f"    Modal btn: '{txt}' visible={mb.is_visible()}")
                if "create" in txt or "ok" in txt or "confirm" in txt:
                    mb.click()
                    print(f"    Clicked: {txt}")
                    time.sleep(5)
                    break

    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8_after_modal.png")

    # Look for API key in page
    print(f"\n[7] Looking for API key...")
    body = page.inner_text("body")
    key_match = re.search(r'sk-[A-Za-z0-9._-]+', body)
    if key_match:
        print(f" ✅ API KEY: {key_match.group(0)}")
    else:
        print(f" ❌ No sk- key found")
        # Check inputs
        for inp in page.query_selector_all("input"):
            val = inp.get_attribute("value") or ""
            if val.startswith("sk-"):
                print(f" ✅ API KEY (input): {val}")
                break
        # Print last part of body
        print(f"  Body (last 1500 chars):\n{body[-1500:]}")

    print("\n[DONE]")
