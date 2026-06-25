#!/usr/bin/env python3
"""Debug step 4: inspect page after Sign Up click."""
import time, random, string
from camoufox.sync_api import Camoufox

REGISTER_URL = "https://account.alibabacloud.com/register/intl_register.htm"

def find_frame(page):
    for f in page.frames:
        if "passport" in f.url or "enter_fill" in f.url or "register" in f.url:
            return f
    return None

email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@REDACTED"
pw = "Abc123!@#Xyz99"
print(f"Email: {email}")

with Camoufox(headless=False, geoip=True) as browser:
    page = browser.new_page()
    page.goto(REGISTER_URL, timeout=120000, wait_until="domcontentloaded")
    page.wait_for_selector("iframe[src*='passport']", timeout=30000)
    time.sleep(3)
    
    frame = find_frame(page)
    
    # Step 2: Individual — might not always appear
    label = None
    for _ in range(15):
        label = frame.query_selector("label:has-text('Individual')")
        if label and label.is_visible(): break
        # Check if we're already on email page
        if frame.query_selector("#email"):
            print("Already on email page (no account type selection)")
            label = "skip"
            break
        time.sleep(2)
        frame = find_frame(page)
    
    if label and label != "skip":
        label.click()
        time.sleep(1)
        next_link = frame.query_selector("a:has-text('Next')")
        if next_link:
            next_link.click()
            print("Clicked Next")
        time.sleep(5)
    elif label == "skip":
        print("Skipping account type — already on email form")
    else:
        print("ERROR: No Individual label and no email field")
        page.screenshot(path="/home/ubuntu/alibaba-farm/error_stuck.png")
        # List all visible text
        for f in page.frames:
            if "about:blank" in f.url: continue
            try:
                els = f.query_selector_all("label, span, div, button, a")
                for el in els[:20]:
                    if el.is_visible():
                        txt = el.inner_text()[:60]
                        if txt.strip():
                            print(f"  TEXT: {txt}")
            except: pass
    
    # Step 3: Fill + submit
    frame = find_frame(page)
    frame.query_selector("#email").fill(email)
    frame.query_selector("#password").fill(pw)
    frame.query_selector("#confirmPwd").fill(pw)
    
    btns = frame.query_selector_all("button")
    for b in btns:
        if "sign up" in b.inner_text().lower():
            b.click()
            print("Clicked Sign Up")
            break
    time.sleep(3)
    
    # Now inspect what happened — check every 3 seconds for 30 seconds
    for i in range(10):
        time.sleep(3)
        print(f"\n=== Check {i} (t={i*3+3}s) ===")
        print(f"Main page URL: {page.url[:100]}")
        page.screenshot(path=f"/home/ubuntu/alibaba-farm/step4_check_{i}.png")
        
        # List all frames
        for fi, f in enumerate(page.frames):
            furl = f.url[:100]
            if "about:blank" in furl: continue
            print(f"  frame[{fi}]: {furl}")
            try:
                vis_els = f.query_selector_all("input, button, a, [role='button'], [role='radio'], label, select, span, div")
                count = 0
                for el in vis_els:
                    vis = el.is_visible()
                    if not vis: continue
                    tag = el.evaluate("e => e.tagName")
                    txt = ""
                    try: txt = el.inner_text()[:60]
                    except: pass
                    t = el.get_attribute("type") or ""
                    n = el.get_attribute("name") or ""
                    iid = el.get_attribute("id") or ""
                    if txt or tag in ("INPUT","SELECT"):
                        print(f"    <{tag}> type={t} name={n} id={iid} text='{txt}'")
                        count += 1
                    if count > 25: break
            except: pass
        
        # Also check main page directly
        try:
            main_vis = page.query_selector_all("input, button, [role='button'], select")
            for el in main_vis[:10]:
                vis = el.is_visible()
                if not vis: continue
                tag = el.evaluate("e => e.tagName")
                txt = ""
                try: txt = el.inner_text()[:60]
                except: pass
                t = el.get_attribute("type") or ""
                print(f"  MAIN <{tag}> type={t} text='{txt}'")
        except: pass
