#!/usr/bin/env python3
"""
Full flow: register → verify email → create API key.
Step 4: Switch to "By Email" + select Singapore + Send
"""
import time, random, string, json, re, imaplib, email as emailmod
from email.header import decode_header
from camoufox.sync_api import Camoufox

REGISTER_URL = "https://account.alibabacloud.com/register/intl_register.htm"
MODELSTUDIO_URL = "https://modelstudio.console.alibabacloud.com/"

GMAIL_USER = "REDACTED"
GMAIL_APP_PW = "REDACTED"

def find_frame(page):
    for f in page.frames[1:]:
        if "passport.alibabacloud.com" in f.url:
            return f
    return None

def read_otp(target_email, timeout=120):
    print(f"[IMAP] Waiting for OTP to {target_email}...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(GMAIL_USER, GMAIL_APP_PW)
            mail.select("INBOX")
            status, messages = mail.search(None, '(FROM "alibaba")')
            msg_ids = messages[0].split()
            for mid in msg_ids[-10:]:
                status, data = mail.fetch(mid, "(RFC822)")
                msg = emailmod.message_from_bytes(data[0][1])
                to_addr = msg.get("To", "").lower()
                if target_email.lower() not in to_addr:
                    continue
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ct = part.get_content_type()
                        if ct == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8","replace")
                            break
                        elif ct == "text/html" and not body:
                            body = part.get_payload(decode=True).decode("utf-8","replace")
                else:
                    body = msg.get_payload(decode=True).decode("utf-8","replace")
                otp = re.search(r'\b(\d{6})\b', body)
                if otp:
                    code = otp.group(1)
                    print(f"[IMAP] Found OTP: {code}")
                    mail.logout()
                    return code
            mail.logout()
        except Exception as e:
            print(f"[IMAP] Error: {e}")
        time.sleep(5)
    print("[IMAP] Timeout")
    return None

test_email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@REDACTED"
test_pw = "Te!t9" + ''.join(random.choices(string.ascii_letters + string.digits, k=10))
print(f"Email: {test_email}")
print(f"Password: {test_pw}")

with Camoufox(headless=False, geoip=True, locale="en-US", humanize=True) as browser:
    page = browser.new_page()
    
    api_log = []
    def on_response(response):
        if "passport.alibabacloud.com" in response.url:
            try: body = response.text()
            except: body = ""
            if body and len(body) < 1000:
                api_log.append({"url": response.url[:100], "body": body[:300]})
    page.on("response", on_response)
    
    # ── Step 1-3: Register ──────────────────────────────
    print("\n[1-3] Registering...")
    page.goto(REGISTER_URL, timeout=120000, wait_until="domcontentloaded")
    page.wait_for_selector("iframe[src*='passport']", timeout=30000)
    time.sleep(5)
    
    frame = find_frame(page)
    for _ in range(15):
        label = frame.query_selector("label:has-text('Individual')")
        if label and label.is_visible(): break
        time.sleep(2)
        frame = find_frame(page)
    label.click()
    time.sleep(2)
    frame.query_selector("a:has-text('Next')").click()
    time.sleep(5)
    
    frame = find_frame(page)
    frame.query_selector("#email").type(test_email, delay=30)
    frame.query_selector("#password").type(test_pw, delay=30)
    frame.query_selector("#confirmPwd").type(test_pw, delay=30)
    time.sleep(1)
    
    for b in frame.query_selector_all("button"):
        if "sign up" in b.inner_text().lower():
            b.click()
            break
    
    # Wait for verification page
    print("[4] Waiting for verification page...")
    time.sleep(15)
    page.screenshot(path="/home/ubuntu/alibaba-farm/step4_verify.png")
    
    frame = find_frame(page)
    if not frame:
        print("ERROR: No frame!")
        exit()
    
    # ─ Step 4: Switch to "By Email" ────────────
    print("[4] Switching to By Email...")
    
    # Tab kedua (index 1) = email mode. Tab pertama = "By Phone" (active)
    # Tab kedua hanya punya SVG icon, no text
    tabs = frame.query_selector_all("li[role='tab']")
    print(f"[4] Found {len(tabs)} tabs")
    if len(tabs) >= 2:
        tabs[1].click()
        print("[4] Clicked tab[1] (email mode)")
        time.sleep(3)
    else:
        print("[4] ERROR: Less than 2 tabs!")
    
    page.screenshot(path="/home/ubuntu/alibaba-farm/step4_email_mode.png")
    
    # ── Step 5: Select Singapore + Send ──────────────────
    print("[5] Selecting Singapore...")
    frame = find_frame(page)
    
    # Find country select
    country_select = frame.query_selector("#country") or frame.query_selector("select[name='country']")
    if country_select:
        # Get all options
        options = country_select.query_selector_all("option")
        for opt in options:
            if "singapore" in opt.inner_text().lower():
                val = opt.get_attribute("value")
                country_select.select_option(value=val)
                print(f"[5] Selected Singapore (value={val})")
                break
        time.sleep(2)
    else:
        print("[5] No country select found!")
    
    page.screenshot(path="/home/ubuntu/alibaba-farm/step5_singapore.png")
    
    # Click Send
    frame = find_frame(page)
    send_btn = None
    for el in frame.query_selector_all("button, a, [role='button']"):
        txt = el.inner_text()[:40].lower()
        if "send" in txt and el.is_visible():
            send_btn = el
            break
    
    if send_btn:
        send_btn.click()
        print(f"[5] Clicked: {send_btn.inner_text()[:40]}")
        time.sleep(3)
    else:
        print("[5] No Send button found!")
    
    page.screenshot(path="/home/ubuntu/alibaba-farm/step5_sent.png")
    
    # ── Step 6: Read OTP ────────────────────────────────
    print("\n[6] Reading OTP...")
    otp = read_otp(test_email, timeout=120)
    
    if otp:
        print(f"[6] OTP: {otp}")
        # Fill OTP
        frame = find_frame(page)
        code_input = frame.query_selector("input[name*='code']") or \
                     frame.query_selector("input[placeholder*='code']") or \
                     frame.query_selector("input[name*='verif']") or \
                     frame.query_selector("input[id*='code']")
        if code_input:
            code_input.fill(otp)
            print("[6] Filled OTP")
        else:
            # Maybe multiple single-digit inputs
            inputs = [i for i in frame.query_selector_all("input") if i.is_visible() and (i.get_attribute("type") or "text") == "text"]
            if len(inputs) >= 6:
                for i, d in enumerate(otp):
                    inputs[i].fill(d)
                print("[6] Filled OTP digits")
        
        # Check agreement
        checkbox = frame.query_selector("input[type='checkbox']")
        if checkbox and not checkbox.is_checked():
            checkbox.click()
            print("[6] Checked agreement")
        
        # Click Sign Up / Confirm
        for el in frame.query_selector_all("button, [role='button']"):
            txt = el.inner_text()[:50].lower()
            if ("sign up" in txt or "confirm" in txt or "register" in txt) and el.is_visible():
                el.click()
                print(f"[6] Clicked: {el.inner_text()[:40]}")
                break
        
        time.sleep(10)
        page.screenshot(path="/home/ubuntu/alibaba-farm/step6_registered.png")
        print(f"\n[6] Page URL: {page.url[:100]}")
        
        # ── Step 7: Navigate to Model Studio ─────────────
        print("\n[7] Navigating to Model Studio...")
        page.goto(MODELSTUDIO_URL, timeout=120000, wait_until="domcontentloaded")
        time.sleep(15)
        page.screenshot(path="/home/ubuntu/alibaba-farm/step7_modelstudio.png")
        print(f"[7] URL: {page.url[:100]}")
        
        # ── Step 8: Create API Key ───────────────────────
        print("\n[8] Creating API Key...")
        
        # Look for "Create API Key" button
        for attempt in range(5):
            for el in page.query_selector_all("button, [role='button'], a"):
                txt = el.inner_text()[:80].lower()
                if "create" in txt and "api" in txt and el.is_visible():
                    el.click()
                    print(f"[8] Clicked: {el.inner_text()[:60]}")
                    time.sleep(3)
                    break
            time.sleep(2)
        
        page.screenshot(path="/home/ubuntu/alibaba-farm/step8_create.png")
        
        # Look for second create button
        for el in page.query_selector_all("button, [role='button']"):
            txt = el.inner_text()[:80].lower()
            if "create" in txt and "api" in txt and el.is_visible():
                el.click()
                print(f"[8] Clicked: {el.inner_text()[:60]}")
                time.sleep(3)
                break
        
        # Click OK (empty description)
        for el in page.query_selector_all("button, [role='button']"):
            txt = el.inner_text()[:40].lower()
            if "ok" in txt and el.is_visible():
                el.click()
                print(f"[8] Clicked: {el.inner_text()[:40]}")
                time.sleep(3)
                break
        
        page.screenshot(path="/home/ubuntu/alibaba-farm/step8_apikey.png")
        
        # ── Step 9: Extract API Key ──────────────────────
        print("\n[9] Extracting API Key...")
        page_text = page.inner_text("body")
        
        api_key_match = re.search(r'sk-[A-Za-z0-9._-]+', page_text)
        if api_key_match:
            api_key = api_key_match.group(0)
            print(f"\n[9] ✅ API KEY: {api_key}")
        else:
            # Check inputs
            for inp in page.query_selector_all("input"):
                val = inp.get_attribute("value") or ""
                if val.startswith("sk-"):
                    print(f"\n[9] ✅ API KEY: {val}")
                    api_key = val
                    break
            else:
                print("[9] No API key found in page")
                print(f"[9] Page text (last 500): {page_text[-500:]}")
                api_key = "NOT_FOUND"
        
        # Save result
        result = {"email": test_email, "password": test_pw, "api_key": api_key}
        with open("/home/ubuntu/alibaba-farm/result.json", "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n[DONE] Result: {json.dumps(result, indent=2)}")
    else:
        print("[6] No OTP received!")
        page.screenshot(path="/home/ubuntu/alibaba-farm/no_otp.png")
    
    # Print API log
    print(f"\n=== API LOG ({len(api_log)}) ===")
    for r in api_log:
        print(f"  {r['url']}")
        print(f"  {r['body']}")
