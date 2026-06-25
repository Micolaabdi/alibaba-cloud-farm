#!/usr/bin/env python3
"""Debug step 8-9 — navigate directly to API key page (skip login, try session).
If not logged in, try login with iframe-aware approach."""

import time
import re
import json
from camoufox.sync_api import Camoufox

EMAIL = "osmqjscx8k@REDACTED"
PASSWORD = "Te!t9aO0vdTwEOB"
APIKEY_URL = "https://modelstudio.console.alibabacloud.com/ap-southeast-1?tab=api"
LOGIN_URL = "https://signin.alibabacloud.com/login.htm"

def find_login_frame(page):
    """Find passport/signin iframe."""
    for f in page.frames[1:]:
        if "passport" in f.url or "signin" in f.url:
            return f
    return None

with Camoufox(headless=False, geoip=True, humanize=True, locale="en-US") as browser:
    page = browser.new_page()

    # Step 1: Try direct navigation to API key page first
    print("[1] Trying direct API key page (session may be valid)...")
    page.goto(APIKEY_URL, timeout=120000, wait_until="domcontentloaded")
    time.sleep(15)
    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8c_direct.png")
    print(f"[1] URL: {page.url}")

    body = page.inner_text("body")[:2000]
    print(f"[1] Body:\n{body[:500]}")

    # Check if redirected to login
    if "sign in" in body.lower() or "login" in body.lower() or "signin" in page.url.lower():
        print("[1] Redirected to login. Need to login first.")

        # Go to login page
        page.goto(LOGIN_URL, timeout=120000, wait_until="domcontentloaded")
        time.sleep(5)
        page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8c_login.png")
        print(f"[1] Login URL: {page.url}")

        # Find login iframe
        frame = find_login_frame(page)
        if not frame:
            print("[1] No passport iframe, trying main page")
            frame = page

        print(f"[1] Frame URL: {frame.url}")

        # List all inputs in frame
        inputs = frame.query_selector_all("input")
        for i, inp in enumerate(inputs):
            t = inp.get_attribute("type") or "text"
            n = inp.get_attribute("name") or ""
            iid = inp.get_attribute("id") or ""
            vis = inp.is_visible()
            print(f"  input[{i}]: type={t} name={n} id={iid} visible={vis}")

        # Fill email — try multiple selectors
        email_filled = False
        for sel in ["input[type='email']", "input[name='email']", "input[name='account']",
                     "input#username", "input[placeholder*='email']", "input[placeholder*='Email']",
                     "input[placeholder*='account']", "input.frm-input"]:
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
            # Try clicking on tab "By Email" if present
            tabs = frame.query_selector_all("li[role='tab'], .tab, [role='tab']")
            for t in tabs:
                txt = t.inner_text()[:50].lower()
                if "email" in txt:
                    t.click()
                    print(f"[1] Clicked email tab: {txt}")
                    time.sleep(2)
                    break
            # Retry
            for sel in ["input[type='email']", "input[name='email']", "input[name='account']",
                         "input#username", "input[placeholder*='email']"]:
                el = frame.query_selector(sel)
                if el:
                    try:
                        el.fill(EMAIL)
                        print(f"[1] Filled email via {sel} (after tab)")
                        email_filled = True
                        break
                    except:
                        pass

        # Fill password
        pw_el = frame.query_selector("input[type='password']") or \
                frame.query_selector("input[name='password']")
        if pw_el:
            try:
                pw_el.fill(PASSWORD)
                print("[1] Filled password")
            except:
                print("[1] Password fill failed")

        # Click Sign In
        for b in frame.query_selector_all("button, [role='button'], input[type='submit']"):
            try:
                txt = b.inner_text().lower()
            except:
                txt = ""
            val = (b.get_attribute("value") or "").lower()
            if "sign in" in txt or "login" in txt or "sign in" in val:
                b.click()
                print(f"[1] Clicked Sign In")
                break

        time.sleep(10)
        page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8c_after_login.png")
        print(f"[1] After login URL: {page.url}")

        # Now navigate to API key page
        print("\n[2] Navigating to API key page after login...")
        page.goto(APIKEY_URL, timeout=120000, wait_until="domcontentloaded")
        time.sleep(15)
        page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8c_apikey.png")
        print(f"[2] URL: {page.url}")
        body = page.inner_text("body")[:2000]
        print(f"[2] Body:\n{body[:500]}")

    # Step 3: Inspect API key page
    print(f"\n[3] Inspecting API key page...")
    print(f"[3] URL: {page.url}")
    print(f"[3] Frames: {len(page.frames)}")
    for i, f in enumerate(page.frames):
        print(f"  frame[{i}]: {f.url[:150]}")

    # All visible buttons
    print(f"\n[4] All visible buttons:")
    btns = page.query_selector_all("button, [role='button'], a")
    for b in btns:
        try:
            txt = b.inner_text()[:100].strip()
            vis = b.is_visible()
            if vis and txt:
                print(f"  BTN: '{txt}'")
        except:
            pass

    # Search for API key related text
    print(f"\n[5] Searching for API key elements...")
    for b in btns:
        try:
            txt = b.inner_text()[:100].lower()
            if ("api" in txt and "key" in txt) or "create" in txt or "generate" in txt:
                vis = b.is_visible()
                print(f"  MATCH: '{b.inner_text()[:100]}' visible={vis}")
        except:
            pass

    # Click Create button
    print(f"\n[6] Trying to click Create API Key...")
    for b in btns:
        try:
            txt = b.inner_text()[:100].lower()
            vis = b.is_visible()
            if vis and (("create" in txt and "api" in txt) or ("create" in txt and "key" in txt)):
                print(f"  Clicking: '{b.inner_text()[:100]}'")
                b.click()
                time.sleep(3)
                page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8c_create_clicked.png")
                break
            elif vis and "create" in txt:
                print(f"  Clicking (generic create): '{b.inner_text()[:100]}'")
                b.click()
                time.sleep(3)
                page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8c_create_clicked.png")
                break
        except:
            pass

    # Check modal
    print(f"\n[7] Checking for modal...")
    time.sleep(3)
    modals = page.query_selector_all("[class*='modal'], [role='dialog'], [class*='dialog']")
    for m in modals:
        try:
            if m.is_visible():
                txt = m.inner_text()[:500]
                print(f"  Modal: {txt}")
                m_btns = m.query_selector_all("button, [role='button']")
                for mb in m_btns:
                    mt = mb.inner_text()[:80].lower()
                    print(f"    Modal btn: '{mt}' visible={mb.is_visible()}")
                    if "create" in mt or "ok" in mt or "confirm" in mt:
                        mb.click()
                        print(f"    Clicked: {mt}")
                        time.sleep(5)
                        break
        except:
            pass

    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8c_after_modal.png")

    # Extract API key
    print(f"\n[8] Looking for API key...")
    body = page.inner_text("body")
    key_match = re.search(r'sk-[A-Za-z0-9._-]+', body)
    if key_match:
        print(f" ✅ API KEY: {key_match.group(0)}")
    else:
        print(" ❌ No sk- key in body text")
        # Check inputs
        for inp in page.query_selector_all("input"):
            val = inp.get_attribute("value") or ""
            if val.startswith("sk-"):
                print(f" ✅ API KEY (input): {val}")
                break
        # Print relevant part of body
        for line in body.split('\n'):
            if 'sk-' in line or 'api' in line.lower() or 'key' in line.lower():
                print(f"  >> {line[:200]}")

    print("\n[DONE]")
