#!/usr/bin/env python3
"""
Full flow with humanize=True — check what happens after success response.
"""
import time, random, string, json, re
from camoufox.sync_api import Camoufox

REGISTER_URL = "https://account.alibabacloud.com/register/intl_register.htm"
MODELSTUDIO_URL = "https://modelstudio.console.alibabacloud.com/"

def find_frame(page):
    for f in page.frames[1:]:
        if "passport.alibabacloud.com" in f.url:
            return f
    return None

email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@REDACTED"
pw = "Te!t9" + ''.join(random.choices(string.ascii_letters + string.digits, k=10))
print(f"Email: {email}")
print(f"Password: {pw}")

with Camoufox(headless=False, geoip=True, locale="en-US", humanize=True) as browser:
    page = browser.new_page()
    
    api_responses = []
    def on_response(response):
        if "passport.alibabacloud.com" in response.url or "nocaptcha" in response.url:
            try:
                body = response.text()
            except:
                body = ""
            if body and len(body) < 2000:
                api_responses.append({"url": response.url[:120], "status": response.status, "body": body[:500]})
    page.on("response", on_response)
    
    print("\n=== Step 1: Load register page ===")
    page.goto(REGISTER_URL, timeout=120000, wait_until="domcontentloaded")
    page.wait_for_selector("iframe[src*='passport']", timeout=30000)
    time.sleep(5)
    
    frame = find_frame(page)
    
    # Step 2: Individual
    print("=== Step 2: Select Individual ===")
    for _ in range(15):
        label = frame.query_selector("label:has-text('Individual')")
        if label and label.is_visible(): break
        time.sleep(2)
        frame = find_frame(page)
    label.click()
    time.sleep(2)
    frame.query_selector("a:has-text('Next')").click()
    time.sleep(5)
    
    # Step 3: Fill + Sign Up
    print("=== Step 3: Fill email/password + Sign Up ===")
    frame = find_frame(page)
    frame.query_selector("#email").type(email, delay=30)
    frame.query_selector("#password").type(pw, delay=30)
    frame.query_selector("#confirmPwd").type(pw, delay=30)
    time.sleep(1)
    
    btns = frame.query_selector_all("button")
    for b in btns:
        if "sign up" in b.inner_text().lower():
            b.click()
            print("Clicked Sign Up")
            break
    
    # Wait and check what happens
    print("\n=== Waiting for response (20s) ===")
    time.sleep(20)
    
    page.screenshot(path="/home/ubuntu/alibaba-farm/after_signup.png")
    
    # Check current state
    frame = find_frame(page)
    print(f"\nFrame URL: {frame.url[:120]}" if frame else "No frame!")
    
    if frame:
        # List ALL visible elements
        print("\n=== Visible elements after Sign Up ===")
        vis_els = frame.query_selector_all("input, button, a, [role='button'], label, select, span, div, h1, h2, p, option")
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
            if txt.strip() or tag in ("INPUT","SELECT","OPTION"):
                print(f"  <{tag}> type={t} name={n} id={iid} role={role} text='{txt}'")
                count += 1
            if count > 50: break
        
        # Specifically look for:
        # 1. Email/phone toggle
        # 2. Country select
        # 3. Send button
        # 4. Verification code input
        print("\n=== Looking for verification elements ===")
        
        # Email/phone toggle
        toggles = frame.query_selector_all("[role='radio'], [role='tab'], [class*='tab'], [class*='toggle']")
        for t in toggles:
            if t.is_visible():
                txt = t.inner_text()[:60]
                if txt.strip():
                    print(f"  TOGGLE: {txt}")
        
        # Selects
        selects = frame.query_selector_all("select")
        for s in selects:
            if s.is_visible():
                opts = s.query_selector_all("option")
                opt_texts = [o.inner_text()[:30] for o in opts[:5]]
                print(f"  SELECT: options={opt_texts}")
        
        # Send button
        for el in frame.query_selector_all("button, a, [role='button']"):
            txt = el.inner_text()[:50].lower()
            if "send" in txt and el.is_visible():
                print(f"  SEND BUTTON: {el.inner_text()[:50]}")
        
        # Code input
        for el in frame.query_selector_all("input"):
            t = el.get_attribute("type") or ""
            n = (el.get_attribute("name") or "").lower()
            p = (el.get_attribute("placeholder") or "").lower()
            iid = (el.get_attribute("id") or "").lower()
            if "code" in n or "code" in p or "code" in iid or "verif" in n or "verif" in p:
                print(f"  CODE INPUT: name={n} id={iid} placeholder={p}")
    
    # Print API responses
    print(f"\n=== API RESPONSES ({len(api_responses)}) ===")
    for r in api_responses:
        print(f"  {r['status']} {r['url'][:80]}")
        print(f"  Body: {r['body'][:200]}")
    
    # Save frame HTML
    if frame:
        html = frame.evaluate("() => document.body ? document.body.innerHTML : ''")
        with open("/home/ubuntu/alibaba-farm/after_signup_html.txt", "w") as f:
            f.write(html[:30000])
        print(f"\nHTML saved ({len(html)} chars)")
