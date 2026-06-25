#!/usr/bin/env python3
"""Debug step 4: inspect page state AFTER Sign Up click."""
import time, random, string
from camoufox.sync_api import Camoufox

REGISTER_URL = "https://account.alibabacloud.com/register/intl_register.htm"

def find_frame(page):
    for f in page.frames[1:]:
        if "passport.alibabacloud.com" in f.url:
            return f
    return None

email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@REDACTED"
pw = "Abc123!@#Xyz99"
print(f"Email: {email}")

with Camoufox(headless=False, geoip=True, locale="en-US") as browser:
    page = browser.new_page()
    page.goto(REGISTER_URL, timeout=120000, wait_until="domcontentloaded")
    page.wait_for_selector("iframe[src*='passport']", timeout=30000)
    time.sleep(3)
    
    frame = find_frame(page)
    
    # Step 2: Individual
    for _ in range(15):
        label = frame.query_selector("label:has-text('Individual')")
        if label and label.is_visible(): break
        time.sleep(2)
        frame = find_frame(page)
    label.click()
    time.sleep(1)
    frame.query_selector("a:has-text('Next')").click()
    time.sleep(5)
    
    # Step 3: Fill + submit
    frame = find_frame(page)
    frame.query_selector("#email").fill(email)
    frame.query_selector("#password").fill(pw)
    frame.query_selector("#confirmPwd").fill(pw)
    
    btns = frame.query_selector_all("button")
    for b in btns:
        if "sign up" in b.inner_text().lower():
            b.click()
            print("Clicked Sign Up (Step 1 of 2)")
            break
    
    # Wait and inspect — check every 3 seconds for 30s
    for i in range(10):
        time.sleep(3)
        print(f"\n=== Check {i} (t={i*3+3}s) ===")
        print(f"Main URL: {page.url[:100]}")
        page.screenshot(path=f"/home/ubuntu/alibaba-farm/step4_debug_{i}.png")
        
        # List all frames
        for fi, f in enumerate(page.frames):
            if "about:blank" in f.url: continue
            print(f"  frame[{fi}]: {f.url[:100]}")
        
        # Check passport frame
        frame = find_frame(page)
        if frame:
            print(f"  Passport frame URL: {frame.url[:100]}")
            vis_els = frame.query_selector_all("input, button, a, [role='button'], [role='radio'], label, select, span, div, h1, h2, p")
            count = 0
            for el in vis_els:
                vis = el.is_visible()
                if not vis: continue
                tag = el.evaluate("e => e.tagName")
                txt = ""
                try: txt = el.inner_text()[:80]
                except: pass
                t = el.get_attribute("type") or ""
                n = el.get_attribute("name") or ""
                iid = el.get_attribute("id") or ""
                role = el.get_attribute("role") or ""
                if txt.strip() or tag in ("INPUT","SELECT"):
                    print(f"    <{tag}> type={t} name={n} id={iid} role={role} text='{txt}'")
                    count += 1
                if count > 30: break
        else:
            print("  No passport frame found!")
            # Check main page
            vis_els = page.query_selector_all("input, button, [role='button'], select, label")
            for el in vis_els[:15]:
                vis = el.is_visible()
                if not vis: continue
                tag = el.evaluate("e => e.tagName")
                txt = ""
                try: txt = el.inner_text()[:60]
                except: pass
                t = el.get_attribute("type") or ""
                print(f"  MAIN <{tag}> type={t} text='{txt}'")
