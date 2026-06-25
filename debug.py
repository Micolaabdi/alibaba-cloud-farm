#!/usr/bin/env python3
"""Debug: inspect Alibaba Cloud register iframe structure."""
import time
from camoufox.sync_api import Camoufox

REGISTER_URL = "https://account.alibabacloud.com/register/intl_register.htm"

def find_frame(page):
    for f in page.frames:
        if "passport" in f.url or "enter_fill_email" in f.url:
            return f
    return None

with Camoufox(headless=False, geoip=True) as browser:
    page = browser.new_page()
    page.goto(REGISTER_URL, timeout=120000, wait_until="domcontentloaded")
    time.sleep(5)
    
    frame = None
    for i in range(30):
        frame = find_frame(page)
        if frame: break
        time.sleep(2)
    
    print(f"Frame URL: {frame.url}")
    
    # Get ALL elements with their text, tag, type, visibility
    elements = frame.query_selector_all("input, button, a, [role='button'], [role='radio'], [role='checkbox'], label, span, div")
    print(f"\nTotal elements: {len(elements)}")
    
    for i, el in enumerate(elements[:80]):
        tag = el.evaluate("e => e.tagName")
        t = el.get_attribute("type") or ""
        n = el.get_attribute("name") or ""
        iid = el.get_attribute("id") or ""
        cls = (el.get_attribute("class") or "")[:40]
        role = el.get_attribute("role") or ""
        vis = el.is_visible()
        txt = ""
        try: txt = el.inner_text()[:40]
        except: pass
        if tag in ("INPUT", "BUTTON", "A") or role in ("button","radio","checkbox") or vis:
            print(f"  [{i}] <{tag}> type={t} name={n} id={iid} role={role} class='{cls}' vis={vis} text='{txt}'")
    
    # Also get full HTML of body
    html = frame.evaluate("() => document.body ? document.body.innerHTML : document.documentElement.innerHTML")
    # Save to file
    with open("/home/ubuntu/alibaba-farm/frame_html.txt", "w") as f:
        f.write(html[:20000])
    print(f"\nHTML saved ({len(html)} chars)")
    
    page.screenshot(path="/home/ubuntu/alibaba-farm/debug_full.png")
