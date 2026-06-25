#!/usr/bin/env python3
"""Debug step 4c: try JS click, check for slider/captcha, intercept network."""
import time, random, string
from camoufox.sync_api import Camoufox

REGISTER_URL = "https://account.alibabacloud.com/register/intl_register.htm"

def find_frame(page):
    for f in page.frames[1:]:
        if "passport.alibabacloud.com" in f.url:
            return f
    return None

email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@REDACTED"
pw = "Te!t9" + ''.join(random.choices(string.ascii_letters + string.digits, k=10))
print(f"Email: {email}")
print(f"Password: {pw}")

with Camoufox(headless=False, geoip=True, locale="en-US") as browser:
    page = browser.new_page()
    
    # Listen for API calls
    api_calls = []
    def on_response(response):
        url = response.url
        if "passport" in url or "register" in url or "signup" in url or "verify" in url:
            api_calls.append(f"API: {response.status} {url[:100]}")
    page.on("response", on_response)
    
    page.goto(REGISTER_URL, timeout=120000, wait_until="domcontentloaded")
    page.wait_for_selector("iframe[src*='passport']", timeout=30000)
    time.sleep(5)
    
    frame = find_frame(page)
    
    # Step 2: Individual
    for _ in range(15):
        label = frame.query_selector("label:has-text('Individual')")
        if label and label.is_visible(): break
        time.sleep(2)
        frame = find_frame(page)
    label.click()
    time.sleep(2)
    frame.query_selector("a:has-text('Next')").click()
    time.sleep(5)
    
    # Step 3: Fill
    frame = find_frame(page)
    frame.query_selector("#email").type(email, delay=30)
    frame.query_selector("#password").type(pw, delay=30)
    frame.query_selector("#confirmPwd").type(pw, delay=30)
    time.sleep(1)
    
    # Find Sign Up button and inspect it
    btns = frame.query_selector_all("button")
    signup_btn = None
    for b in btns:
        if "sign up" in b.inner_text().lower():
            signup_btn = b
            # Get button details
            print(f"Button tag: {b.evaluate('e => e.tagName')}")
            print(f"Button type: {b.get_attribute('type')}")
            print(f"Button class: {b.get_attribute('class')}")
            print(f"Button id: {b.get_attribute('id')}")
            print(f"Button onclick: {b.get_attribute('onclick')}")
            print(f"Button disabled: {b.get_attribute('disabled')}")
            print(f"Button text: {b.inner_text()}")
            
            # Check parent form
            parent_form = b.evaluate("""e => {
                let p = e.parentElement;
                while(p) {
                    if(p.tagName === 'FORM') return p.outerHTML.slice(0, 200);
                    p = p.parentElement;
                }
                return 'NO FORM FOUND';
            }""")
            print(f"Parent form: {parent_form}")
            break
    
    # Check for captcha/slider elements
    print("\n=== Checking for captcha/slider ===")
    captcha_els = frame.query_selector_all("[class*='captcha'], [class*='slider'], [class*='verify'], [id*='captcha'], [id*='slider'], [id*='nc_'], .nc_wrapper, #aliyunCaptcha")
    print(f"Found {len(captcha_els)} captcha-related elements:")
    for c in captcha_els:
        vis = c.is_visible()
        tag = c.evaluate("e => e.tagName")
        cls = c.get_attribute("class") or ""
        iid = c.get_attribute("id") or ""
        print(f"  <{tag}> id={iid} class={cls} vis={vis}")
    
    # Also check iframes for captcha
    for f in page.frames:
        if "captcha" in f.url or "slider" in f.url or "nocaptcha" in f.url:
            print(f"  CAPTCHA FRAME: {f.url[:100]}")
    
    # Try JS click
    print("\n=== Trying JS click ===")
    if signup_btn:
        signup_btn.evaluate("e => e.click()")
        print("JS click done")
    
    time.sleep(5)
    page.screenshot(path="/home/ubuntu/alibaba-farm/step4c_after_js_click.png")
    
    # Check if page changed
    frame = find_frame(page)
    if frame:
        url = frame.url
        print(f"Frame URL: {url[:100]}")
        # Check for verify/country/send
        has_verify = frame.query_selector("input[placeholder*='code']") or frame.query_selector("input[name*='code']")
        has_country = frame.query_selector("select")
        all_els = frame.query_selector_all("button, a, [role='button']")
        send_texts = []
        for el in all_els:
            txt = el.inner_text()[:40]
            if el.is_visible():
                send_texts.append(txt)
        print(f"verify={has_verify}, country={has_country}")
        print(f"Buttons: {send_texts}")
    
    # Print API calls
    print(f"\n=== API calls ({len(api_calls)}) ===")
    for c in api_calls[-20:]:
        print(f"  {c}")
