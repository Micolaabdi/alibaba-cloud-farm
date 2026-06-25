#!/usr/bin/env python3
"""
Intercept ALL network calls when clicking Sign Up.
Capture: endpoint, method, headers, post_data, response.
Goal: find the API endpoint that submits registration.
"""
import time, random, string, json
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
    
    # Capture ALL requests
    requests_log = []
    def on_request(request):
        url = request.url
        # Skip static assets
        if any(url.endswith(ext) for ext in [".js",".css",".png",".jpg",".gif",".svg",".woff",".woff2",".ico"]):
            return
        if "doubleclick" in url or "google" in url or "linkedin" in url or "facebook" in url or "taobao.com" in url:
            return
        req = {
            "method": request.method,
            "url": url[:200],
            "headers": dict(request.headers),
            "post_data": request.post_data,
        }
        requests_log.append(req)
        print(f"  >> {request.method} {url[:120]}")
        if request.post_data:
            print(f"     POST: {request.post_data[:200]}")
    
    def on_response(response):
        url = response.url
        if any(url.endswith(ext) for ext in [".js",".css",".png",".jpg",".gif",".svg",".woff",".woff2",".ico"]):
            return
        if "doubleclick" in url or "google" in url or "linkedin" in url or "facebook" in url or "taobao.com" in url:
            return
        try:
            body = response.text()[:500]
        except:
            body = "[binary]"
        print(f"  << {response.status} {url[:120]}")
        if body and body != "[binary]" and len(body) > 2:
            print(f"     RESP: {body[:300]}")
    
    page.on("request", on_request)
    page.on("response", on_response)
    
    print("\n=== Loading page ===")
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
    
    # Step 3: Fill form
    frame = find_frame(page)
    frame.query_selector("#email").type(email, delay=30)
    frame.query_selector("#password").type(pw, delay=30)
    frame.query_selector("#confirmPwd").type(pw, delay=30)
    time.sleep(1)
    
    print("\n=== Clicking Sign Up ===")
    btns = frame.query_selector_all("button")
    for b in btns:
        if "sign up" in b.inner_text().lower():
            b.click()
            print("Clicked!")
            break
    
    # Wait for network activity
    print("\n=== Waiting for network (15s) ===")
    time.sleep(15)
    
    # Summary
    print(f"\n=== TOTAL REQUESTS CAPTURED: {len(requests_log)} ===")
    for i, req in enumerate(requests_log):
        print(f"\n[{i}] {req['method']} {req['url']}")
        if req['post_data']:
            print(f"  POST_DATA: {req['post_data'][:500]}")
        # Print interesting headers
        hdrs = req['headers']
        for k in ['content-type','x-csrf-token','x-requested-with','authorization','cookie','referer','origin']:
            if k in hdrs:
                val = hdrs[k][:150]
                print(f"  {k}: {val}")
    
    # Save full log
    with open("/home/ubuntu/alibaba-farm/network_log.json", "w") as f:
        json.dump(requests_log, f, indent=2, default=str)
    print("\nFull log saved to network_log.json")
