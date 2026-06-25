#!/usr/bin/env python3
"""Debug v2: wait for iframe element then access frame."""
import time
from camoufox.sync_api import Camoufox

REGISTER_URL = "https://account.alibabacloud.com/register/intl_register.htm"

with Camoufox(headless=False, geoip=True) as browser:
    page = browser.new_page()
    print("Navigating...")
    page.goto(REGISTER_URL, timeout=120000, wait_until="domcontentloaded")
    
    # Wait for iframe element to appear in DOM
    print("Waiting for iframe...")
    try:
        iframe_el = page.wait_for_selector("iframe[src*='passport']", timeout=30000)
        print(f"Found iframe element: src={iframe_el.get_attribute('src')[:80]}")
    except Exception as e:
        print(f"wait_for_selector failed: {e}")
        # Try all iframes
        iframes = page.query_selector_all("iframe")
        print(f"Found {len(iframes)} iframes:")
        for i, ifr in enumerate(iframes):
            src = ifr.get_attribute("src") or ""
            print(f"  iframe[{i}]: src={src[:80]}")
    
    time.sleep(3)
    
    # Now find frame
    for attempt in range(10):
        for f in page.frames:
            if "passport" in f.url or "enter_fill" in f.url:
                print(f"Found frame: {f.url[:100]}")
                # Get inputs
                inputs = f.query_selector_all("input")
                print(f"  {len(inputs)} inputs")
                for inp in inputs:
                    t = inp.get_attribute("type") or ""
                    n = inp.get_attribute("name") or ""
                    iid = inp.get_attribute("id") or ""
                    vis = inp.is_visible()
                    ph = inp.get_attribute("placeholder") or ""
                    print(f"    type={t} name={n} id={iid} ph={ph} vis={vis}")
                
                # Get all visible elements with text
                vis_els = f.query_selector_all("button, [role='button'], [role='radio'], label, a, span")
                for el in vis_els[:30]:
                    tag = el.evaluate("e => e.tagName")
                    role = el.get_attribute("role") or ""
                    vis = el.is_visible()
                    txt = ""
                    try: txt = el.inner_text()[:50]
                    except: pass
                    if vis and txt:
                        print(f"    <{tag}> role={role} vis={vis} text='{txt}'")
                
                # Save HTML
                html = f.evaluate("() => document.body ? document.body.innerHTML : ''")
                with open("/home/ubuntu/alibaba-farm/frame_html.txt", "w") as fh:
                    fh.write(html[:30000])
                print(f"  HTML saved ({len(html)} chars)")
                break
        else:
            print(f"  attempt {attempt+1}: no frame yet, frames={[f.url[:50] for f in page.frames]}")
            time.sleep(2)
            continue
        break
    
    page.screenshot(path="/home/ubuntu/alibaba-farm/debug_v2.png")
    print("Done")
