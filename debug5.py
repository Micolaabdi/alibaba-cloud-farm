#!/usr/bin/env python3
"""Debug: inspect account.alibabacloud.com registration flow."""
import time
from camoufox.sync_api import Camoufox

URL = "https://account.alibabacloud.com/"

def find_frame(page):
    for f in page.frames:
        if "passport" in f.url or "register" in f.url or "login" in f.url or "account" in f.url:
            return f
    return None

with Camoufox(headless=False, geoip=True, locale="en-US") as browser:
    page = browser.new_page()
    print(f"Navigating to {URL}...")
    page.goto(URL, timeout=120000, wait_until="domcontentloaded")
    time.sleep(8)
    
    print(f"\nMain page URL: {page.url}")
    print(f"Title: {page.title()}")
    page.screenshot(path="/home/ubuntu/alibaba-farm/account_home.png")
    
    # List all frames
    print(f"\nFrames: {len(page.frames)}")
    for i, f in enumerate(page.frames):
        if "about:blank" in f.url: continue
        print(f"  frame[{i}]: {f.url[:120]}")
    
    # Check main page for buttons/links
    print("\n=== Main page visible elements ===")
    vis_els = page.query_selector_all("button, a, [role='button'], input, label, span, div")
    count = 0
    for el in vis_els:
        vis = el.is_visible()
        if not vis: continue
        tag = el.evaluate("e => e.tagName")
        txt = ""
        try: txt = el.inner_text()[:80]
        except: pass
        t = el.get_attribute("type") or ""
        href = el.get_attribute("href") or ""
        if txt.strip() or tag in ("INPUT",):
            print(f"  <{tag}> type={t} text='{txt}' href={href[:60]}")
            count += 1
        if count > 40: break
    
    # Check frames
    for fi, f in enumerate(page.frames[1:], 1):
        if "about:blank" in f.url: continue
        print(f"\n=== Frame[{fi}]: {f.url[:80]} ===")
        try:
            vis_els = f.query_selector_all("button, a, [role='button'], input, label, span, div")
            count = 0
            for el in vis_els:
                vis = el.is_visible()
                if not vis: continue
                tag = el.evaluate("e => e.tagName")
                txt = ""
                try: txt = el.inner_text()[:80]
                except: pass
                t = el.get_attribute("type") or ""
                if txt.strip() or tag in ("INPUT",):
                    print(f"  <{tag}> type={t} text='{txt}'")
                    count += 1
                if count > 30: break
        except Exception as e:
            print(f"  Error: {e}")
    
    # Look for "Register" or "Sign Up" or "Create" links/buttons
    print("\n=== Looking for registration links ===")
    all_links = page.query_selector_all("a")
    for a in all_links:
        txt = a.inner_text()[:50].lower()
        href = a.get_attribute("href") or ""
        if any(k in txt for k in ["register", "sign up", "signup", "create", "new"]):
            print(f"  LINK: '{a.inner_text()[:50]}' -> {href[:100]}")
    
    # Also check for Free Trial / Sign Up buttons
    all_btns = page.query_selector_all("button, [role='button']")
    for b in all_btns:
        txt = b.inner_text()[:50].lower()
        if any(k in txt for k in ["register", "sign up", "signup", "create", "free", "trial"]):
            print(f"  BUTTON: '{b.inner_text()[:50]}'")
