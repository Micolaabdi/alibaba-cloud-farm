#!/usr/bin/env python3
"""Debug step 8 — login via 'Logon with Cloud Account' then navigate to API Key page."""

import time
import re
from camoufox.sync_api import Camoufox

EMAIL = "osmqjscx8k@REDACTED"
PASSWORD = "Te!t9aO0vdTwEOB"
LOGIN_URL = "https://signin.alibabacloud.com/login.htm"
APIKEY_URL = "https://modelstudio.console.alibabacloud.com/ap-southeast-1?tab=api"

with Camoufox(headless=False, geoip=True, humanize=True, locale="en-US") as browser:
    page = browser.new_page()

    # Step 1: Login
    print("[1] Navigating to login page...")
    page.goto(LOGIN_URL, timeout=120000, wait_until="domcontentloaded")
    time.sleep(5)
    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8e_login.png")
    print(f"[1] URL: {page.url}")

    # Click "Logon with Cloud Account" link
    for a in page.query_selector_all("a"):
        try:
            txt = a.inner_text()[:80].lower()
            if "cloud" in txt and "account" in txt:
                a.click()
                print(f"[1] Clicked: '{a.inner_text()[:80]}'")
                time.sleep(5)
                break
        except:
            pass

    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8e_cloud_login.png")
    print(f"[1] URL after cloud link: {page.url}")

    # Check frames
    print(f"[1] Frames: {len(page.frames)}")
    for i, f in enumerate(page.frames):
        print(f"  frame[{i}]: {f.url[:150]}")

    # Use passport frame if exists, else main page
    frame = page
    for f in page.frames[1:]:
        if "passport" in f.url or "signin" in f.url:
            frame = f
            print(f"[1] Using frame: {frame.url}")
            break

    # List inputs
    inputs = frame.query_selector_all("input")
    print(f"[1] Found {len(inputs)} inputs:")
    for i, inp in enumerate(inputs):
        t = inp.get_attribute("type") or "text"
        n = inp.get_attribute("name") or ""
        iid = inp.get_attribute("id") or ""
        ph = inp.get_attribute("placeholder") or ""
        vis = inp.is_visible()
        print(f"  input[{i}]: type={t} name={n} id={iid} ph={ph} vis={vis}")

    # Fill email
    email_filled = False
    for sel in ["input[type='email']", "input[name='email']", "input[name='account']",
                 "input#username", "input[placeholder*='email']",
                 "input[placeholder*='Email']", "input[placeholder*='account']"]:
        el = frame.query_selector(sel)
        if el:
            try:
                el.fill(EMAIL)
                print(f"[1] Filled email via {sel}")
                email_filled = True
                break
            except:
                pass

    if not email_filled:
        for inp in frame.query_selector_all("input"):
            t = (inp.get_attribute("type") or "text").lower()
            if t in ("text", "email", "") and inp.is_visible():
                inp.fill(EMAIL)
                print(f"[1] Filled email via generic input")
                email_filled = True
                break

    # Fill password
    pw_el = frame.query_selector("input[type='password']")
    if pw_el:
        try:
            pw_el.fill(PASSWORD)
            print("[1] Filled password")
        except:
            print("[1] Password fill failed")

    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8e_filled.png")

    # Click Sign In
    for b in frame.query_selector_all("button, [role='button'], input[type='submit']"):
        try:
            txt = b.inner_text().lower()
        except:
            txt = ""
        val = (b.get_attribute("value") or "").lower()
        if "sign in" in txt or "login" in txt or "log in" in txt or "sign in" in val:
            b.click()
            print(f"[1] Clicked: '{txt}'")
            break

    time.sleep(15)
    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8e_after_login.png")
    print(f"[1] After login URL: {page.url}")

    # Step 2: Navigate to API Key page
    print(f"\n[2] Navigating to API Key page...")
    page.goto(APIKEY_URL, timeout=120000, wait_until="domcontentloaded")
    time.sleep(15)
    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8e_apikey.png")
    print(f"[2] URL: {page.url}")

    body = page.inner_text("body")[:3000]
    print(f"[2] Body (first 1500):\n{body[:1500]}")

    # List visible buttons
    print(f"\n[3] All visible buttons:")
    btns = page.query_selector_all("button, [role='button'], a")
    for b in btns:
        try:
            txt = b.inner_text()[:100].strip()
            if b.is_visible() and txt:
                print(f"  BTN: '{txt}'")
        except:
            pass

    # Click Create
    print(f"\n[4] Clicking Create...")
    for b in btns:
        try:
            txt = b.inner_text()[:100].lower()
            if b.is_visible() and "create" in txt:
                b.click()
                print(f"  Clicked: '{b.inner_text()[:100]}'")
                time.sleep(3)
                page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8e_create.png")
                break
        except:
            pass

    # Modal
    print(f"\n[5] Checking modal...")
    time.sleep(3)
    modals = page.query_selector_all("[class*='modal'], [role='dialog'], [class*='Dialog']")
    for m in modals:
        try:
            if m.is_visible():
                txt = m.inner_text()[:500]
                print(f"  Modal: {txt[:300]}")
                m_btns = m.query_selector_all("button, [role='button']")
                for mb in m_btns:
                    mt = mb.inner_text()[:80].lower()
                    print(f"    btn: '{mt}' vis={mb.is_visible()}")
                    if ("create" in mt or "ok" in mt or "confirm" in mt) and mb.is_visible():
                        mb.click()
                        print(f"    Clicked: {mt}")
                        time.sleep(5)
                        break
        except:
            pass

    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8e_after_modal.png")

    # Extract key
    print(f"\n[6] Looking for API key...")
    body = page.inner_text("body")
    key_match = re.search(r'sk-[A-Za-z0-9._-]+', body)
    if key_match:
        print(f" ✅ API KEY: {key_match.group(0)}")
    else:
        print(" ❌ No sk- in body")
        for inp in page.query_selector_all("input"):
            val = inp.get_attribute("value") or ""
            if val.startswith("sk-"):
                print(f" ✅ API KEY (input): {val}")
                break
        for line in body.split('\n'):
            if 'sk-' in line or ('api' in line.lower() and 'key' in line.lower()):
                print(f"  >> {line[:200]}")

    print("\n[DONE]")
