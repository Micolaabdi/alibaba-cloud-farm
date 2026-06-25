#!/usr/bin/env python3
"""Debug step 4: what happens after Sign Up click."""
import time, random, string
from camoufox.sync_api import Camoufox

REGISTER_URL = "https://account.alibabacloud.com/register/intl_register.htm"

def find_frame(page):
    for f in page.frames:
        if "passport" in f.url or "enter_fill" in f.url:
            return f
    return None

email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@REDACTED"
pw = "Abc123!@#XYZ123"
print(f"Email: {email}")

with Camoufox(headless=False, geoip=True) as browser:
    page = browser.new_page()
    page.goto(REGISTER_URL, timeout=120000, wait_until="domcontentloaded")
    page.wait_for_selector("iframe[src*='passport']", timeout=30000)
    time.sleep(3)
    
    frame = find_frame(page)
    print(f"Frame: {frame.url[:80]}")
    
    # Wait for Individual label to appear
    print("Waiting for Individual label...")
    for attempt in range(15):
        label = frame.query_selector("label:has-text('Individual')")
        if label:
            break
        time.sleep(2)
        frame = find_frame(page)
        if not frame:
            print("Frame lost!")
            break
    if not label:
        print("ERROR: Individual label never appeared")
        page.screenshot(path="/home/ubuntu/alibaba-farm/error_no_label.png")
    else:
        label.click()
        time.sleep(1)
        frame.query_selector("a:has-text('Next')").click()
        time.sleep(5)
        
        # Step 3: Fill + submit
        frame = find_frame(page)
        frame.query_selector("#email").fill(email)
        frame.query_selector("#password").fill(pw)
        frame.query_selector("#confirmPwd").fill(pw)
    
    # Find and click Sign Up
    all_btns = frame.query_selector_all("button, [role='button'], input[type='submit']")
    for b in all_btns:
        txt = b.inner_text().lower() if b.inner_text() else (b.get_attribute("value") or "").lower()
        if "sign" in txt or "register" in txt:
            print(f"Clicking: {txt}")
            b.click()
            break
    time.sleep(2)
    
    # Take screenshots every 2 seconds for 20 seconds
    for i in range(10):
        time.sleep(2)
        page.screenshot(path=f"/home/ubuntu/alibaba-farm/step4_debug_{i}.png")
        frame = find_frame(page)
        if frame:
            url = frame.url
            print(f"[{i}] Frame URL: {url[:100]}")
            # List ALL visible elements
            vis_els = frame.query_selector_all("input, button, a, [role='button'], [role='radio'], label, select, span, div")
            for el in vis_els:
                tag = el.evaluate("e => e.tagName")
                vis = el.is_visible()
                if not vis:
                    continue
                t = el.get_attribute("type") or ""
                n = el.get_attribute("name") or ""
                iid = el.get_attribute("id") or ""
                role = el.get_attribute("role") or ""
                txt = ""
                try: txt = el.inner_text()[:60]
                except: pass
                if txt or tag in ("INPUT","SELECT","BUTTON"):
                    print(f"  <{tag}> type={t} name={n} id={iid} role={role} text='{txt}'")
        else:
            print(f"[{i}] No frame! Main URL: {page.url[:80]}")
            # Check main page
            vis_els = page.query_selector_all("input, button, a, [role='button'], label, select")
            for el in vis_els[:15]:
                tag = el.evaluate("e => e.tagName")
                vis = el.is_visible()
                if not vis: continue
                txt = ""
                try: txt = el.inner_text()[:60]
                except: pass
                t = el.get_attribute("type") or ""
                print(f"  MAIN <{tag}> type={t} vis={vis} text='{txt}'")
    
    # Save final frame HTML
    frame = find_frame(page)
    if frame:
        html = frame.evaluate("() => document.body ? document.body.innerHTML : ''")
        with open("/home/ubuntu/alibaba-farm/step4_html.txt", "w") as f:
            f.write(html[:30000])
        print(f"HTML saved ({len(html)} chars)")
