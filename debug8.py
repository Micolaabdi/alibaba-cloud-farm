#!/usr/bin/env python3
"""Debug step 8 — inspect Model Studio page to find Create API Key button."""

import time
import json
from camoufox.sync_api import Camoufox

MODELSTUDIO_URL = "https://modelstudio.console.alibabacloud.com/"

with Camoufox(headless=False, geoip=True, humanize=True, locale="en-US") as browser:
    page = browser.new_page()
    print("[1] Navigating to Model Studio...")
    page.goto(MODELSTUDIO_URL, timeout=120000, wait_until="domcontentloaded")

    # Wait for page to fully load
    print("[2] Waiting 15s for page render...")
    time.sleep(15)
    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8_initial.png")

    # Check current URL
    print(f"[3] Current URL: {page.url}")

    # Check if redirected to login
    body_text = page.inner_text("body")[:2000]
    print(f"[4] Body text (first 2000 chars):\n{body_text}")

    # List ALL frames
    print(f"\n[5] Frames ({len(page.frames)}):")
    for i, f in enumerate(page.frames):
        print(f"  frame[{i}]: {f.url[:150]}")

    # Search all frames for "API" or "Key" text
    print("\n[6] Searching for API Key elements in all frames...")
    for i, frame in enumerate(page.frames):
        try:
            btns = frame.query_selector_all("button, [role='button'], a, span, div")
            for b in btns:
                try:
                    txt = b.inner_text()[:100].lower()
                    if ("api" in txt and "key" in txt) or "create" in txt:
                        vis = b.is_visible()
                        print(f"  frame[{i}] MATCH: '{txt}' visible={vis} tag={b.evaluate('el => el.tagName')}")
                except:
                    pass
        except:
            pass

    # Check for modal/popup
    print("\n[7] Checking for modals/dialogs...")
    modals = page.query_selector_all("[class*='modal'], [class*='dialog'], [class*='popup'], [role='dialog']")
    print(f"  Found {len(modals)} modal-like elements")
    for m in modals:
        print(f"  modal: {m.get_attribute('class')[:80]} visible={m.is_visible()}")

    # Try clicking sidebar menu items
    print("\n[8] Looking for sidebar/navigation items...")
    nav_items = page.query_selector_all("a, [role='menuitem'], [role='tab'], .nav-item, .menu-item")
    for n in nav_items[:30]:
        txt = n.inner_text()[:80].lower()
        if any(k in txt for k in ["api", "key", "credential", "token", "settings"]):
            print(f"  NAV: '{txt}' href={n.get_attribute('href')}")

    # Wait more and check again
    print("\n[9] Waiting 10s more...")
    time.sleep(10)
    page.screenshot(path="/home/ubuntu/alibaba-farm/dbg8_after_wait.png")

    # Re-check body
    body_text2 = page.inner_text("body")[:2000]
    if body_text2 != body_text:
        print(f"[10] Page changed! New body:\n{body_text2}")
    else:
        print("[10] Page unchanged")

    # Check for any visible text containing "API"
    print("\n[11] All visible text containing 'API':")
    all_els = page.query_selector_all("*")
    found = set()
    for el in all_els[:500]:
        try:
            txt = el.inner_text()[:200]
            if "api" in txt.lower() and len(txt) < 200:
                if txt not in found:
                    found.add(txt)
                    vis = el.is_visible()
                    if vis:
                        print(f"  VISIBLE: '{txt[:100]}'")
        except:
            pass

    print("\n[DONE] Check screenshots: dbg8_initial.png, dbg8_after_wait.png")
