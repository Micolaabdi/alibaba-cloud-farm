#!/usr/bin/env python3
"""
Solve Alibaba NoCaptcha slider after it appears.
Strategy: drag slider button from left to right with human-like motion.
"""
import time, random, string, json, re
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

with Camoufox(headless=False, geoip=True, locale="en-US", humanize=True) as browser:
    page = browser.new_page()
    
    api_responses = []
    def on_response(response):
        if "check_enter_email" in response.url or "nocaptcha" in response.url:
            try:
                body = response.text()
            except:
                body = ""
            api_responses.append({"url": response.url[:120], "status": response.status, "body": body[:500]})
            if "success" in body.lower() and "ret" not in body:
                print(f">>> {response.status} {response.url[:80]}")
                print(f"    {body[:200]}")
    page.on("response", on_response)
    
    print("\n=== Loading page ===")
    page.goto(REGISTER_URL, timeout=120000, wait_until="domcontentloaded")
    page.wait_for_selector("iframe[src*='passport']", timeout=30000)
    time.sleep(5)
    
    frame = find_frame(page)
    
    # Individual → Next → Fill → Sign Up
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
    frame.query_selector("#email").type(email, delay=30)
    frame.query_selector("#password").type(pw, delay=30)
    frame.query_selector("#confirmPwd").type(pw, delay=30)
    time.sleep(1)
    
    # Click Sign Up
    btns = frame.query_selector_all("button")
    for b in btns:
        if "sign up" in b.inner_text().lower():
            b.click()
            print("Clicked Sign Up")
            break
    
    # Wait for slider to appear
    print("\n=== Waiting for slider ===")
    slider_frame = None
    for i in range(15):
        time.sleep(2)
        # Check for punish/captcha iframe
        for f in page.frames:
            if "punish" in f.url or "nocaptcha" in f.url:
                slider_frame = f
                print(f"Found captcha frame: {f.url[:80]}")
                break
        if slider_frame:
            break
        
        # Also check if risk_slider is visible in main passport frame
        frame = find_frame(page)
        if frame:
            risk = frame.query_selector("#risk_slider_container")
            if risk and risk.is_visible():
                print(f"Risk slider visible in passport frame")
                slider_frame = frame
                break
    
    if not slider_frame:
        print("ERROR: No slider found!")
        page.screenshot(path="/home/ubuntu/alibaba-farm/no_slider.png")
        exit()
    
    time.sleep(3)
    page.screenshot(path="/home/ubuntu/alibaba-farm/slider_before.png")
    
    # Inspect slider structure
    print("\n=== Slider frame elements ===")
    all_els = slider_frame.query_selector_all("*")
    slider_els = []
    for el in all_els:
        vis = el.is_visible()
        if not vis: continue
        tag = el.evaluate("e => e.tagName")
        cls = (el.get_attribute("class") or "")
        iid = el.get_attribute("id") or ""
        txt = ""
        try: txt = el.inner_text()[:40]
        except: pass
        if tag in ("DIV","SPAN","BUTTON","INPUT","A") and (cls or iid):
            slider_els.append({"tag": tag, "id": iid, "class": cls[:40], "vis": vis, "text": txt})
    
    for e in slider_els[:30]:
        print(f"  <{e['tag']}> id={e['id']} class={e['class']} text='{e['text']}'")
    
    # Look for slider handle/button
    slider_handle = slider_frame.query_selector("#nc_1_n1z") or \
                    slider_frame.query_selector(".nc_iconfont") or \
                    slider_frame.query_selector("[class*='btn_slide']") or \
                    slider_frame.query_selector("[class*='slider-btn']") or \
                    slider_frame.query_selector("[class*='handle']") or \
                    slider_frame.query_selector("button") or \
                    slider_frame.query_selector("[role='slider']")
    
    if slider_handle:
        print(f"\n=== Found slider handle: {slider_handle.evaluate('e => e.outerHTML')[:200]}")
        
        # Get position
        box = slider_handle.bounding_box()
        print(f"Handle position: {box}")
        
        if box:
            # Drag from left to right with human-like motion
            start_x = box["x"] + box["width"] / 2
            start_y = box["y"] + box["height"] / 2
            
            # Get the slider track width
            track = slider_frame.query_selector("#nc_1__scale_text") or \
                    slider_frame.query_selector("[class*='scale']") or \
                    slider_frame.query_selector("[class*='track']")
            track_box = track.bounding_box() if track else None
            end_x = (track_box["x"] + track_box["width"] - box["width"]/2) if track_box else (start_x + 300)
            
            print(f"Dragging from ({start_x:.0f}, {start_y:.0f}) to ({end_x:.0f}, {start_y:.0f})")
            
            # Human-like drag: move mouse, press, move in steps, release
            page.mouse.move(start_x, start_y)
            time.sleep(0.3)
            page.mouse.down()
            time.sleep(0.2)
            
            # Move in steps with random delays
            steps = 30
            for s in range(steps + 1):
                progress = s / steps
                # Ease-out curve
                eased = 1 - (1 - progress) ** 2
                x = start_x + (end_x - start_x) * eased
                # Small random Y variation
                y = start_y + random.uniform(-2, 2)
                page.mouse.move(x, y)
                time.sleep(random.uniform(0.02, 0.05))
            
            time.sleep(0.2)
            page.mouse.up()
            print("Drag completed!")
            
            time.sleep(5)
            page.screenshot(path="/home/ubuntu/alibaba-farm/slider_after.png")
            
            # Check result
            print("\n=== API responses after slider ===")
            for r in api_responses[-10:]:
                print(f"  {r['status']} {r['url'][:80]}")
                print(f"  {r['body'][:200]}")
            
            # Check if we moved to verification page
            frame = find_frame(page)
            if frame:
                has_verify = frame.query_selector("input[placeholder*='code']") or frame.query_selector("input[name*='code']")
                has_select = frame.query_selector("select")
                has_send = False
                for el in frame.query_selector_all("button, a, [role='button']"):
                    if "send" in el.inner_text().lower() and el.is_visible():
                        has_send = True
                        break
                print(f"\nVerification page: verify={has_verify}, select={has_select}, send={has_send}")
    else:
        print("\nNo slider handle found!")
        # Maybe it's a different type of captcha
        page.screenshot(path="/home/ubuntu/alibaba-farm/no_handle.png")
        # Check all visible text
        for f in page.frames:
            if "about:blank" in f.url: continue
            try:
                els = f.query_selector_all("div, span, p, button")
                for el in els[:15]:
                    if el.is_visible():
                        txt = el.inner_text()[:60]
                        if txt.strip():
                            print(f"  TEXT: {txt}")
            except: pass
