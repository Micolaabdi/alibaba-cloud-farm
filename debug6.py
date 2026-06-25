#!/usr/bin/env python3
"""Debug: click Sign Up Now from account page, then inspect register flow."""
import time, random, string
from camoufox.sync_api import Camoufox

URL = "https://account.alibabacloud.com/"

def find_frame(page):
    """Find passport iframe — must be actual child frame, not main page."""
    for f in page.frames[1:]:  # Skip main frame (index 0)
        furl = f.url
        if "passport.alibabacloud.com" in furl:
            return f
    return None

email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@REDACTED"
pw = "Abc123!@#Xyz99"
print(f"Email: {email}")

with Camoufox(headless=False, geoip=True, locale="en-US") as browser:
    page = browser.new_page()
    
    # Go to account page first
    print("1. Opening account.alibabacloud.com...")
    page.goto(URL, timeout=120000, wait_until="domcontentloaded")
    time.sleep(5)
    
    # Click "Sign Up Now" link
    print("2. Clicking Sign Up Now...")
    signup_link = page.query_selector("a:has-text('Sign Up Now')")
    if not signup_link:
        signup_link = page.query_selector("a:has-text('Sign Up')")
    if signup_link:
        signup_link.click()
        print("   Clicked Sign Up link")
    else:
        print("   ERROR: No Sign Up link found!")
        page.screenshot(path="/home/ubuntu/alibaba-farm/error_no_signup.png")
        exit()
    
    time.sleep(8)
    print(f"3. After click URL: {page.url}")
    page.screenshot(path="/home/ubuntu/alibaba-farm/after_signup_click.png")
    
    # Wait for passport frame
    frame = None
    for i in range(15):
        frame = find_frame(page)
        if frame: break
        time.sleep(2)
    
    if not frame:
        print("   ERROR: No passport frame!")
        for f in page.frames:
            if "about:blank" not in f.url:
                print(f"   frame: {f.url[:100]}")
        exit()
    
    print(f"   Frame: {frame.url[:100]}")
    
    # Wait for content to load
    time.sleep(5)
    
    # Inspect frame — what do we see?
    print("\n4. Frame visible elements:")
    vis_els = frame.query_selector_all("input, button, a, [role='button'], [role='radio'], label, select, span, div, h1, h2, h3, p")
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
            print(f"  <{tag}> type={t} name={n} id={iid} role={role} text='{txt}'")
            count += 1
        if count > 40: break
    
    # Save frame HTML
    html = frame.evaluate("() => document.body ? document.body.innerHTML : ''")
    with open("/home/ubuntu/alibaba-farm/register_frame_html.txt", "w") as f:
        f.write(html[:30000])
    print(f"\n5. Frame HTML saved ({len(html)} chars)")
    
    # Check if we see Individual/Enterprise or email form
    if frame.query_selector("label:has-text('Individual')"):
        print("\n✅ On account type selection page (Individual/Enterprise)")
    elif frame.query_selector("#email"):
        print("\n✅ On email/password form directly")
    else:
        print("\n❓ Unknown page state")
