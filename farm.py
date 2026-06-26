#!/usr/bin/env python3
"""
Alibaba Cloud account farm — Camoufox automation with proxy.
Loop: register → verify email → create API key.
If slider appears → skip + restart from beginning.
"""

import sys
import time
import json
import imaplib
import email
import re
import random
import string
import math
import os
import subprocess
from email.header import decode_header
from camoufox.sync_api import Camoufox

# ─ uinput virtual mouse for slider solve ─
try:
    import uinput
    UINPUT_AVAILABLE = True
except Exception:
    UINPUT_AVAILABLE = False

# ─ Global virtual mouse ─
_virtual_mouse = None

# ─ Config ───────────
# IMAP credentials — set via environment variables.
# For Gmail: use an App Password (NOT your regular password).
# Enable 2FA → Google Account → Security → App passwords.
#
# You also need a catch-all domain that forwards to your Gmail.
# Set up catch-all forwarding in your domain DNS (e.g. Cloudflare email routing).
#
# Required env vars:
#   IMAP_USER    — your Gmail address (e.g. you@gmail.com)
#   IMAP_PASS    — Gmail App Password (spaces ok, e.g. "abcd efgh ijkl mnop")
#   EMAIL_DOMAIN — your catch-all domain (e.g. yourdomain.com)
#
# Copy .env.example to .env and fill in your values, OR export them in your shell.

IMAP_USER = os.environ.get("IMAP_USER", "")
IMAP_PASS = os.environ.get("IMAP_PASS", "")
EMAIL_DOMAIN = os.environ.get("EMAIL_DOMAIN", "")
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))

# Try loading from .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
    IMAP_USER = os.environ.get("IMAP_USER", IMAP_USER)
    IMAP_PASS = os.environ.get("IMAP_PASS", IMAP_PASS)
    EMAIL_DOMAIN = os.environ.get("EMAIL_DOMAIN", EMAIL_DOMAIN)
    IMAP_HOST = os.environ.get("IMAP_HOST", IMAP_HOST)
    IMAP_PORT = int(os.environ.get("IMAP_PORT", str(IMAP_PORT)))
except ImportError:
    pass

# Validate required config
if not IMAP_USER or not IMAP_PASS or not EMAIL_DOMAIN:
    print("=" * 60)
    print("ERROR: IMAP credentials not configured!")
    print()
    print("Set these environment variables (or create a .env file):")
    print("  IMAP_USER=your@gmail.com")
    print("  IMAP_PASS=your-app-password")
    print("  EMAIL_DOMAIN=your-catchall-domain.com")
    print()
    print("For Gmail App Passwords:")
    print(" 1. Enable 2FA: Google Account → Security → 2-Step Verification")
    print(" 2. Generate:   Google Account → Security → App passwords")
    print()
    print("For catch-all domain:")
    print("  Set up email forwarding for *@yourdomain.com → your@gmail.com")
    print("  (e.g. Cloudflare Email Routing, ImprovMX, etc.)")
    print("=" * 60)
    sys.exit(1)

REGISTER_URL = "https://account.alibabacloud.com/register/intl_register.htm"

MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "20"))  # Max registration attempts per run
RESULTS_FILE = os.environ.get("RESULTS_FILE", "results.json")
MODELSTUDIO_URL = "https://modelstudio.console.alibabacloud.com/"

# ── Helpers ──────────────────────────────────────────────────
def generate_email():
    name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{name}@{EMAIL_DOMAIN}"

def generate_password():
    """Password: letters + digits only, no special chars (causes type issues)."""
    chars = string.ascii_letters + string.digits
    pw = ''.join(random.choices(chars, k=16))
    # Ensure complexity requirements
    pw = "Aa1" + pw  # uppercase, lowercase, digit prefix
    return pw

def read_otp_from_imap(target_email, timeout=120):
    """Read OTP verification code from IMAP — only NEW emails for this email."""
    print(f"[IMAP] Waiting for OTP to {target_email}...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            mail.login(IMAP_USER, IMAP_PASS)
            mail.select("INBOX")
            # Search ALL emails from alibaba, then filter by To header
            status, messages = mail.search(None, '(FROM "alibaba")')
            msg_ids = messages[0].split()
            # Check most recent first
            for mid in reversed(msg_ids[-10:]):
                status, data = mail.fetch(mid, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])
                to_addr = msg.get("To", "").lower()
                if target_email.lower() not in to_addr:
                    continue
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ct = part.get_content_type()
                        if ct == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", "replace")
                            break
                        elif ct == "text/html" and not body:
                            body = part.get_payload(decode=True).decode("utf-8", "replace")
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", "replace")
                # Find OTP — it's in a span with blue color, NOT a CSS hex color
                # Pattern: >NN</span> where NNNN is the code
                otp_match = re.search(r'>\s*(\d{6})\s*</span>', body)
                if not otp_match:
                    # Fallback: look for code near "verification" or "code" text
                    otp_match = re.search(r'(?:code|verification)[^<]*?(\d{6})', body, re.IGNORECASE)
                if not otp_match:
                    # Fallback: find 6-digit number that's NOT 181818 (CSS color) or 999/666666/808080
                    for m in re.finditer(r'\b(\d{6})\b', body):
                        num = m.group(1)
                        if num not in ('181818', '999', '666666', '808080'):
                            otp_match = m
                            break
                if otp_match:
                    code = otp_match.group(1)
                    print(f"[IMAP] Found OTP: {code} for {target_email}")
                    # Mark as seen
                    mail.store(mid, '+FLAGS', '\\Seen')
                    mail.logout()
                    return code
            mail.logout()
        except Exception as e:
            print(f"[IMAP] Error: {e}")
        time.sleep(5)
    print("[IMAP] Timeout waiting for OTP")
    return None


def find_register_frame(page):
    """Find the passport.alibabacloud.com iframe — skip main page frame."""
    for frame in page.frames[1:]:
        if "passport.alibabacloud.com" in frame.url:
            return frame
    return None


def load_results():
    """Load existing results."""
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE) as f:
                return json.load(f)
        except:
            pass
    return []


def save_results(results):
    """Save results to file."""
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)


def safe_screenshot(page, path):
    """Take screenshot safely — won't crash if page is closed."""
    try:
        page.screenshot(path=path)
    except Exception:
        pass


# ── uinput virtual mouse + slider solver ─────────────────────

def setup_virtual_mouse(width=1920, height=1080):
    """Setup uinput virtual mouse for OS-level drag."""
    global _virtual_mouse
    if not UINPUT_AVAILABLE:
        return None
    try:
        subprocess.run(['modprobe', 'uinput'], stderr=subprocess.PIPE, check=False)
        _virtual_mouse = uinput.Device([
            uinput.BTN_LEFT,
            uinput.ABS_X + (0, width, 0, 0),
            uinput.ABS_Y + (0, height, 0, 0),
        ])
        time.sleep(0.5)
        print("[MOUSE] Virtual mouse ready")
        return _virtual_mouse
    except Exception as e:
        print(f"[MOUSE] Setup failed: {e}")
        return None


def _cubic_bezier(t, p0, p1, p2, p3):
    return (
        (1 - t) ** 3 * p0
        + 3 * (1 - t) ** 2 * t * p1
        + 3 * (1 - t) * t ** 2 * p2
        + t ** 3 * p3
    )


def _bezier_path(start_x, end_x, y, steps):
    dist = abs(end_x - start_x)
    cp_off = random.uniform(-8, 8)
    cp1_x = start_x + dist * random.uniform(0.2, 0.4)
    cp1_y = y + cp_off
    cp2_x = start_x + dist * random.uniform(0.6, 0.8)
    cp2_y = y + cp_off * random.uniform(-0.5, 0.5)
    return [
        (_cubic_bezier(i / steps, start_x, cp1_x, cp2_x, end_x),
         _cubic_bezier(i / steps, y, cp1_y, cp2_y, y))
        for i in range(steps + 1)
    ]


def _speed_profile(steps):
    delays = []
    for i in range(steps):
        t = i / max(steps - 1, 1)
        speed = (1 - math.cos(t * math.pi)) / 2
        delays.append(max(0.005, 1.0 - (speed * 0.75) + random.gauss(0, 0.05)))
    return delays


def humanly_drag(mouse, start_x, end_x, y, duration=1.2):
    """Human-behavior slider drag using xdotool (reliable in Xvfb)."""
    import subprocess
    
    steps = max(35, min(int(50 + random.gauss(0, 8)), 80))
    print(f"  [DRAG] {start_x:.0f}→{end_x:.0f}, {steps} steps, {duration:.2f}s (xdotool)")

    # Move to start
    subprocess.run(['xdotool', 'mousemove', str(int(start_x)), str(int(y))], check=False)
    time.sleep(0.3)

    # Mouse down
    subprocess.run(['xdotool', 'mousedown', '1'], check=False)
    time.sleep(0.2)

    # Drag with bezier path + tremor + speed profile
    path = _bezier_path(start_x, end_x, y, steps)
    delays = _speed_profile(steps)

    for i, (px, py) in enumerate(path):
        tremor = 1.2 if i < 5 else (0.6 if i < steps - 5 else 0.4)
        fx = int(round(px + random.gauss(0, tremor)))
        fy = int(round(py + random.gauss(0, tremor * 0.6)))
        subprocess.run(['xdotool', 'mousemove', str(fx), str(fy)], check=False)

        step_delay = (duration / steps) * delays[min(i, len(delays) - 1)]
        if random.random() < 0.04 and 5 < i < steps - 5:
            step_delay *= random.uniform(2.5, 4.0)
        time.sleep(max(0.004, step_delay))

    # Mouse up
    subprocess.run(['xdotool', 'mouseup', '1'], check=False)
    time.sleep(0.3)
    print("  [DRAG] Done")


def humanly_drag_playwright(page, start_x, end_x, y, duration=1.5):
    """Human-behavior slider drag using Playwright mouse API.
    Cross-platform — works on Windows without uinput/xdotool.
    Does NOT move the OS cursor — injects events directly into the browser."""
    steps = max(35, min(int(50 + random.gauss(0, 8)), 80))
    print(f"  [DRAG] {start_x:.0f}→{end_x:.0f}, {steps} steps, {duration:.2f}s (playwright)")

    # Move to start
    page.mouse.move(start_x, y)
    time.sleep(0.3)

    # Mouse down
    page.mouse.down()
    time.sleep(0.2)

    # Drag with bezier path + tremor + speed profile
    path = _bezier_path(start_x, end_x, y, steps)
    delays = _speed_profile(steps)

    for i, (px, py) in enumerate(path):
        tremor = 1.2 if i < 5 else (0.6 if i < steps - 5 else 0.4)
        fx = px + random.gauss(0, tremor)
        fy = py + random.gauss(0, tremor * 0.6)
        page.mouse.move(fx, fy)

        step_delay = (duration / steps) * delays[min(i, len(delays) - 1)]
        if random.random() < 0.04 and 5 < i < steps - 5:
            step_delay *= random.uniform(2.5, 4.0)
        time.sleep(max(0.004, step_delay))

    # Mouse up
    page.mouse.up()
    time.sleep(0.3)
    print("  [DRAG] Done (playwright)")


def _wait_for_punish_iframe(page, timeout=15):
    """Wait for the baxia-dialog-content (punish) iframe to appear and load."""
    for _ in range(timeout):
        for frame in page.frames:
            if "punish" in frame.url or "nocaptcha" in frame.url:
                # Check if frame content has loaded (has body content)
                try:
                    ready = frame.evaluate("() => document.readyState === 'complete' && !!document.querySelector('#nc_1_n1z, .nc_iconfont, .btn_slide')")
                    if ready:
                        return frame
                except:
                    pass
                # Even if not fully ready, return it if URL is set
                if frame.url and "punish" in frame.url:
                    return frame
        time.sleep(1)
    return None


def find_slider_handle(page):
    """Search all frames for baxia slider handle."""
    for frame in page.frames:
        # Skip about:blank frames
        if "about:blank" in frame.url:
            continue
        for sel in ['#nc_1_n1z', '.nc_iconfont.btn_slide', '.btn_slide',
                     'span.nc_iconfont', '[role="slider"]',
                     '.nc_iconfont', 'span.btn_slide']:
            try:
                el = frame.query_selector(sel)
                if el:
                    box = el.bounding_box()
                    if box and box['width'] > 0:
                        return el, frame, sel
            except:
                pass
    return None, None, None


def solve_slider(page, mouse):
    """Find and solve baxia slider.
    Uses uinput+xdotool on Linux, Playwright mouse API on Windows/other."""
    # Determine drag method
    use_playwright = not mouse or not UINPUT_AVAILABLE
    if use_playwright:
        print("  [SLIDER] Using Playwright mouse (no uinput)")
    elif not mouse:
        print("  [SLIDER] No virtual mouse — can't solve")
        return False

    # Step 1: Wait for the punish iframe to appear and load
    punish_frame = _wait_for_punish_iframe(page, timeout=10)
    if punish_frame:
        print(f"  [SLIDER] Punish iframe loaded: {punish_frame.url[:60]}")
    else:
        print("  [SLIDER] No punish iframe — checking all frames")

    # Step 2: Wait for slider handle to appear (increased to 15 retries = 30s)
    el, frame, sel = None, None, None
    for wait in range(15):
        el, frame, sel = find_slider_handle(page)
        if el:
            break
        time.sleep(2)

    if not el:
        print("  [SLIDER] No slider found after 30s")
        safe_screenshot(page, "/home/ubuntu/alibaba-farm/slider_not_found.png")
        return False

    print(f"  [SLIDER] Found '{sel}' in frame {frame.url[:50]}")

    # Get handle position
    box = el.bounding_box()
    if not box:
        print("  [SLIDER] No bounding box")
        return False

    # Get slider track for drag distance
    track = frame.query_selector("#nc_1__scale_text") or \
            frame.query_selector(".nc_scale") or \
            frame.query_selector("#nc_1_n1t")
    if track:
        track_box = track.bounding_box()
        drag_dist = track_box['width'] - box['width']
    else:
        drag_dist = 300

    start_x = box['x'] + box['width'] / 2
    start_y = box['y'] + box['height'] / 2
    end_x = start_x + drag_dist

    print(f"  [SLIDER] Handle at ({start_x:.0f},{start_y:.0f}), drag {drag_dist:.0f}px")
    safe_screenshot(page, "/home/ubuntu/alibaba-farm/slider_before_drag.png")

    # Drag! — use Playwright mouse on Windows, xdotool on Linux
    if use_playwright:
        humanly_drag_playwright(page, start_x, end_x, start_y, duration=1.5)
    else:
        humanly_drag(mouse, start_x, end_x, start_y, duration=1.5)

    time.sleep(3)
    safe_screenshot(page, "/home/ubuntu/alibaba-farm/slider_after_drag.png")

    # Check if slider is gone or success indicator present
    el2, _, _ = find_slider_handle(page)
    if not el2:
        print("  [SLIDER] ✅ SOLVED!")
        return True

    # Fallback: try JS-based drag inside the frame
    print("  [SLIDER] Playwright drag failed — trying JS drag fallback...")
    try:
        js_result = frame.evaluate("""() => {
            const handle = document.querySelector('#nc_1_n1z') || document.querySelector('.btn_slide');
            if (!handle) return 'no handle';
            const track = document.querySelector('#nc_1__scale_text') || document.querySelector('.nc_scale');
            if (!track) return 'no track';
            const box = handle.getBoundingClientRect();
            const trackBox = track.getBoundingClientRect();
            const startX = box.x + box.width / 2;
            const startY = box.y + box.height / 2;
            const endX = trackBox.x + trackBox.width - box.width / 2;
            
            function dispatchMouseEvent(type, x, y) {
                const el = document.elementFromPoint(x, y) || handle;
                const evt = new MouseEvent(type, {
                    bubbles: true, cancelable: true,
                    clientX: x, clientY: y,
                    button: 0, buttons: type === 'mouseup' ? 0 : 1,
                });
                el.dispatchEvent(evt);
            }
            
            dispatchMouseEvent('mousedown', startX, startY);
            const steps = 40;
            for (let i = 0; i <= steps; i++) {
                const t = i / steps;
                const eased = 1 - Math.pow(1 - t, 2);
                const x = startX + (endX - startX) * eased;
                const y = startY + (Math.random() - 0.5) * 2;
                dispatchMouseEvent('mousemove', x, y);
            }
            dispatchMouseEvent('mouseup', endX, startY);
            return 'dragged';
        }""")
        print(f"  [SLIDER] JS drag result: {js_result}")
        time.sleep(3)
    except Exception as e:
        print(f"  [SLIDER] JS drag error: {e}")

    # Final check
    el3, _, _ = find_slider_handle(page)
    if not el3:
        print("  [SLIDER] ✅ SOLVED (via JS fallback)!")
        return True
    else:
        print("  [SLIDER] ❌ Still visible after all attempts")
        return False


def register_one_attempt(browser):
    """Single registration attempt. Returns dict with account info or None if slider."""
    page = browser.new_page()
    
    test_email = generate_email()
    test_password = generate_password()
    print(f"  Email: {test_email}")
    
    # ─ Step 1: Navigate ─
    print("  [1] Navigating...")
    try:
        page.goto(REGISTER_URL, timeout=120000, wait_until="domcontentloaded")
    except Exception as nav_err:
        print(f"  [1] ⚠️ Navigation error: {nav_err}")
        page.close()
        return "FAIL"
    
    # Wait for passport iframe — proxy is slower, wait up to 30s
    frame = None
    for wait in range(15):
        try:
            page.wait_for_selector("iframe[src*='passport']", timeout=5000)
        except:
            pass
        time.sleep(2)
        frame = find_register_frame(page)
        if frame:
            print(f"  [1] Frame found after {wait*2}s")
            break
    if not frame:
        print("  [1] ERROR: No passport frame!")
        page.close()
        return None
    
    # ─ Step 2: Individual + Next ─
    print("  [2] Individual account...")
    label = None
    for _ in range(10):
        label = frame.query_selector("label:has-text('Individual')")
        if label and label.is_visible():
            break
        time.sleep(2)
        frame = find_register_frame(page)
        if not frame:
            break
    if not label:
        print("  [2] ERROR: Individual label not found!")
        page.close()
        return None
    label.click()
    time.sleep(2)
    next_link = frame.query_selector("a:has-text('Next')")
    if next_link:
        next_link.click()
    time.sleep(5)
    
    # ─ Step 3: Fill form + Sign Up ─
    print("  [3] Filling form...")
    frame = find_register_frame(page)
    time.sleep(3)
    
    email_field = frame.query_selector("#email")
    pw_field = frame.query_selector("#password")
    confirm_field = frame.query_selector("#confirmPwd")
    
    if not email_field or not pw_field:
        print("  [3] ERROR: Fields not found!")
        page.close()
        return None
    
    email_field.click()
    time.sleep(0.3)
    for ch in test_email:
        page.keyboard.type(ch, delay=30)
    time.sleep(0.5)
    
    pw_field.click()
    time.sleep(0.3)
    for ch in test_password:
        page.keyboard.type(ch, delay=30)
    time.sleep(0.5)
    
    if confirm_field:
        confirm_field.click()
        time.sleep(0.3)
        for ch in test_password:
            page.keyboard.type(ch, delay=30)
    time.sleep(2)
    
    # Verify password was filled
    pw_val = pw_field.evaluate("el => el.value")
    print(f"  [3] Password verify: len={len(pw_val)} match={pw_val == test_password}")
    
    # Click Sign Up
    signup_btn = None
    for b in frame.query_selector_all("button"):
        if "sign up" in b.inner_text().lower():
            signup_btn = b
            break
    if not signup_btn:
        print("  [3] ERROR: No Sign Up button!")
        page.close()
        return None
    signup_btn.click()
    print("  [3] Clicked Sign Up")
    
    # ─ Check: slider or success ─
    for wait in range(15):
        time.sleep(2)
        frame = find_register_frame(page)
        if not frame:
            continue
        
        tabs = frame.query_selector_all("li[role='tab']")
        if len(tabs) > 0:
            print(f"  [3] ✅ Success! Page advanced ({wait*2}s)")
            break
        
        slider = frame.query_selector("#risk_slider_container")
        if slider and slider.is_visible() and wait >= 3:
            print(f"  [3] ⚠️ Slider detected — attempting solve...")
            if solve_slider(page, _virtual_mouse):
                print(f"  [3] ✅ Slider solved! Checking if page advanced...")
                # Wait for page to process the slider solve (up to 10s)
                advanced = False
                for adv_wait in range(5):
                    time.sleep(2)
                    frame = find_register_frame(page)
                    if frame:
                        tabs = frame.query_selector_all("li[role='tab']")
                        if len(tabs) > 0:
                            print(f"  [3] ✅ Success! Page advanced after slider solve ({(adv_wait+1)*2}s)")
                            advanced = True
                            break
                if advanced:
                    break
            print(f"  [3] ❌ Slider solve failed — SKIP")
            page.close()
            return "SLIDER"
    else:
        print("  [3] ❌ Timeout — no tabs, no slider")
        page.close()
        return None
    
    # ─ Step 4: Email verification tab ─
    print("  [4] Email verification tab...")
    frame = find_register_frame(page)
    tabs = frame.query_selector_all("li[role='tab']")
    if len(tabs) >= 2:
        tabs[1].click()
        print("  [4] Clicked tab[1] (email mode)")
        time.sleep(3)
    else:
        print(f"  [4] WARNING: Only {len(tabs)} tabs")
    
    # ─ Step 5: Singapore + Send ─
    print("  [5] Singapore + Send...")
    frame = find_register_frame(page)
    selects = frame.query_selector_all("select")
    for sel in selects:
        for opt in sel.query_selector_all("option"):
            if "singapore" in opt.inner_text().lower():
                sel.select_option(value=opt.get_attribute("value"))
                print("  [5] Selected Singapore")
                break
    
    # Click Send
    for b in frame.query_selector_all("button, [role='button']"):
        txt = b.inner_text()[:50].lower()
        if "send" in txt and b.is_visible():
            b.click()
            print("  [5] Clicked Send")
            break
    time.sleep(3)
    
    # ─ Step 6: OTP ─
    print("  [6] Reading OTP...")
    otp = read_otp_from_imap(test_email, timeout=120)
    if not otp:
        print("  [6] ERROR: No OTP!")
        page.close()
        return None
    
    frame = find_register_frame(page)
    # OTP is a single input field with id=emailCaptcha
    otp_input = frame.query_selector("#emailCaptcha") or \
                frame.query_selector("input[name='emailCaptcha']") or \
                frame.query_selector("input[placeholder*='code']") or \
                frame.query_selector("input[placeholder*='verification']") or \
                frame.query_selector("input[name*='code']") or \
                frame.query_selector("input[name*='captcha']")
    
    if not otp_input:
        # Fallback: find the visible input that's NOT email/country/checkbox
        all_inputs = frame.query_selector_all("input")
        for inp in all_inputs:
            try:
                if not inp.is_visible():
                    continue
                inp_id = (inp.get_attribute("id") or "").lower()
                inp_name = (inp.get_attribute("name") or "").lower()
                if "email" == inp_id or "email" == inp_name or "country" in inp_id or "country" in inp_name:
                    continue  # Skip email and country fields
                if inp.get_attribute("type") == "checkbox":
                    continue
                otp_input = inp
                print(f"  [6] Found OTP input (fallback): id={inp.get_attribute('id')} name={inp.get_attribute('name')}")
                break
            except:
                pass
    
    if otp_input:
        otp_input.click()
        time.sleep(0.3)
        for ch in otp:
            page.keyboard.type(ch, delay=30)
        time.sleep(0.5)
        # Verify
        otp_val = otp_input.evaluate("el => el.value")
        print(f"  [6] Typed OTP: {otp} (verify: len={len(otp_val)})")
    else:
        print(f"  [6] ❌ No OTP input found!")
        # Debug: list all inputs
        for inp in frame.query_selector_all("input"):
            try:
                print(f"  [6]   INPUT: type={inp.get_attribute('type')} id={inp.get_attribute('id')} name={inp.get_attribute('name')} placeholder={inp.get_attribute('placeholder')} visible={inp.is_visible()}")
            except:
                pass
    
    # Check agreement
    checkbox = frame.query_selector("input[type='checkbox']")
    if checkbox and not checkbox.is_checked():
        checkbox.click()
    
    # Click Sign Up (Step 2)
    for b in frame.query_selector_all("button, [role='button']"):
        txt = b.inner_text().lower()
        if "sign up" in txt or "confirm" in txt or "register" in txt:
            b.click()
            print(f"  [6] Clicked final Sign Up")
            break
    time.sleep(8)
    
    # Verify registration completed — check if page changed
    post_url = page.url
    print(f"  [6] Post-register URL: {post_url}")
    safe_screenshot(page, "/home/ubuntu/alibaba-farm/step6_registered.png")
    
    # Check if still on register page (registration failed)
    if "register" in post_url:
        body = page.inner_text("body")[:1000]
        if "verification code" in body.lower() or "sign up" in body.lower():
            print("  [6] ⚠️ Still on register page — checking for errors...")
            # Maybe OTP wrong or form not submitted
            frame = find_register_frame(page)
            if frame:
                err = frame.query_selector("[class*='error'], [class*='alert'], [class*='msg']")
                if err:
                    print(f"  [6] Error: {err.inner_text()[:200]}")
            print("  [6] ❌ Registration may have failed")
            page.close()
            return None
    
    # ─ Step 7: Open Model Studio (NO LOGIN — Bryan: session carries from register) ─
    print("  [7] Opening Model Studio (no login)...")
    page.goto(MODELSTUDIO_URL, timeout=120000, wait_until="domcontentloaded")
    
    # Wait for SPA to load
    print("  [7] Waiting for SPA load...")
    session_lost = False
    for wait in range(30):
        time.sleep(3)
        body = page.inner_text("body")[:2000]
        if "Sign In" in body or "Enter your email" in body or "log on" in body.lower():
            print(f"  [7] ⚠️ Login page — session lost after {wait*3}s — attempting login...")
            session_lost = True
            break
        if "Dashboard" in body or "Model Studio" in body or "api" in body.lower():
            print(f"  [7] ✅ Model Studio loaded after {wait*3}s")
            break
    
    # ─ Step 7-retry: If session lost, login with new credentials ─
    if session_lost:
        safe_screenshot(page, "/home/ubuntu/alibaba-farm/step7_login_lost.png")
        login_url = "https://account.alibabacloud.com/login.htm"
        print(f"  [7] Navigating to login page: {login_url}")
        page.goto(login_url, timeout=120000, wait_until="domcontentloaded")
        time.sleep(3)
        
        # Find login iframe (same structure as register)
        login_frame = None
        for _ in range(10):
            for f in page.frames[1:]:
                if "passport.alibabacloud.com" in f.url:
                    login_frame = f
                    break
            if login_frame:
                break
            time.sleep(2)
        
        if not login_frame:
            print("  [7] ❌ No login iframe found!")
            page.close()
            return {
                "email": test_email,
                "password": test_password,
                "api_key": "SESSION_LOST",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        print(f"  [7] Found login frame: {login_frame.url[:60]}")
        
        # Fill email
        email_input = login_frame.query_selector("#email") or login_frame.query_selector("input[name='email']")
        if email_input:
            email_input.fill("")
            email_input.type(test_email, delay=30)
            print(f"  [7] Typed email: {test_email}")
        else:
            print("  [7] ❌ No email input in login frame!")
        
        # Fill password
        pw_input = login_frame.query_selector("#password") or login_frame.query_selector("input[type='password']")
        if pw_input:
            pw_input.fill("")
            pw_input.type(test_password, delay=30)
            print(f"  [7] Typed password (len={len(test_password)})")
        
        time.sleep(1)
        
        # Click Sign In / Login button
        for b in login_frame.query_selector_all("button, [role='button']"):
            txt = b.inner_text().lower()
            if "sign in" in txt or "log in" in txt or "login" in txt:
                b.click()
                print(f"  [7] Clicked: '{b.inner_text().strip()}'")
                break
        
        # Wait for login to complete and redirect
        print("  [7] Waiting for login redirect...")
        login_ok = False
        for wait in range(20):
            time.sleep(3)
            current_url = page.url
            body = page.inner_text("body")[:2000]
            if "Sign In" not in body and "Enter your email" not in body:
                if "dashboard" in current_url.lower() or "console" in current_url.lower() or "modelstudio" in current_url.lower() or "account" in current_url.lower():
                    print(f"  [7] ✅ Login successful! URL: {current_url[:80]}")
                    login_ok = True
                    break
            if "captcha" in body.lower() or "slider" in body.lower() or "risk" in body.lower():
                print(f"  [7] ⚠️ Captcha appeared during login — session may be restricted")
                break
        
        if not login_ok:
            print("  [7] ❌ Login failed — SESSION_LOST")
            safe_screenshot(page, "/home/ubuntu/alibaba-farm/step7_login_failed.png")
            page.close()
            return {
                "email": test_email,
                "password": test_password,
                "api_key": "SESSION_LOST",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # Now navigate to Model Studio with established session
        print("  [7] Re-navigating to Model Studio with login session...")
        page.goto(MODELSTUDIO_URL, timeout=120000, wait_until="domcontentloaded")
        time.sleep(5)
        body = page.inner_text("body")[:2000]
        if "Sign In" in body or "Enter your email" in body:
            print("  [7] ❌ Still login page after login+retry — SESSION_LOST")
            safe_screenshot(page, "/home/ubuntu/alibaba-farm/step7_still_lost.png")
            page.close()
            return {
                "email": test_email,
                "password": test_password,
                "api_key": "SESSION_LOST",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        print("  [7] ✅ Model Studio loaded after login!")
    
    safe_screenshot(page, "/home/ubuntu/alibaba-farm/step7_loaded.png")
    
    # ─ Step 7b: Click Dashboard tab in top nav → switches to console view ─
    print("  [7b] Clicking Dashboard tab (top nav)...")
    # Use JS evaluate for speed — Playwright query_selector is slow on large SPAs
    for wait in range(15):
        clicked = page.evaluate("""
            () => {
                const els = document.querySelectorAll('a, span, li, [role="tab"], div');
                for (const el of els) {
                    const txt = (el.innerText || el.textContent || '').trim();
                    if (txt === 'Dashboard') {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            el.click();
                            return true;
                        }
                    }
                }
                return false;
            }
        """)
        if clicked:
            print(f"  [7b] Clicked Dashboard (try {wait+1})")
            break
        time.sleep(2)
    time.sleep(5)
    safe_screenshot(page, "/home/ubuntu/alibaba-farm/step7b_dashboard.png")
    print(f"  [7b] URL after Dashboard: {page.url}")
    
    # ─ Step 7c: Find and click API Key ─
    # Bryan: "pilih api key" — in sidebar under Manage section, need to scroll down
    print("  [7c] Looking for API Key...")
    time.sleep(3)
    
    # First, dismiss any modal/overlay that blocks clicks
    print("  [7c] Dismissing any modal overlay...")
    for _ in range(3):
        page.evaluate("""
            () => {
                // Click close/OK buttons in modals
                const modals = document.querySelectorAll('[class*="modal"], [role="dialog"], [class*="dialog"]');
                for (const m of modals) {
                    const rect = m.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        // Find close/OK button in modal
                        const btns = m.querySelectorAll('button, [role="button"], .ant-modal-close, [class*="close"]');
                        for (const b of btns) {
                            const txt = (b.innerText || '').toLowerCase();
                            if (txt.includes('ok') || txt.includes('close') || txt.includes('got it') || txt.includes('confirm') || txt.includes('got') || b.className.includes('close')) {
                                b.click();
                                return true;
                            }
                        }
                    }
                }
                // Also try pressing Escape
                return false;
            }
        """)
        time.sleep(1)
        # Press Escape to dismiss
        page.keyboard.press("Escape")
        time.sleep(1)
    
    api_key_clicked = False
    
    for search_round in range(4):
        print(f"  [7c] Search round {search_round+1}...")
        
        # Scroll ALL scrollable containers to bottom
        page.evaluate("""
            document.querySelectorAll('*').forEach(el => {
                if (el.scrollHeight > el.clientHeight) {
                    el.scrollTop = el.scrollHeight;
                }
            });
        """)
        time.sleep(2)
        
        # Search for EXACT "API Key" text and click via JS (avoids modal intercept)
        clicked = page.evaluate("""
            () => {
                const els = document.querySelectorAll('a, span, li, [role="menuitem"], button, div, p');
                for (const el of els) {
                    const ownText = Array.from(el.childNodes)
                        .filter(n => n.nodeType === 3)
                        .map(n => n.textContent.trim())
                        .join('');
                    if (ownText === 'API Key' || ownText === 'api-key' || ownText === 'API key') {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            el.click();
                            return true;
                        }
                    }
                }
                for (const el of els) {
                    const txt = (el.innerText || '').trim();
                    if (txt === 'API Key' || txt === 'api-key') {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            el.click();
                            return true;
                        }
                    }
                }
                return false;
            }
        """)
        
        if clicked:
            print(f"  [7c] Clicked API Key (round {search_round+1})")
            api_key_clicked = True
            break
        
        if search_round == 0:
            # Try expanding "Manage" section
            for el in page.query_selector_all("span, div, a"):
                try:
                    txt = el.inner_text().strip().lower()
                    if txt == "manage" and el.is_visible():
                        el.click()
                        print(f"  [7c] Expanded 'Manage' section")
                        time.sleep(2)
                        break
                except:
                    pass
        elif search_round == 2:
            # Try direct URL
            print("  [7c] Trying direct API Key URL...")
            page.goto("https://modelstudio.console.alibabacloud.com/ap-southeast-1?tab=dashboard#/api-key",
                       timeout=60000, wait_until="domcontentloaded")
            time.sleep(5)
    
    if not api_key_clicked:
        # Final check: maybe already on API key page via URL
        body = page.inner_text("body")[:2000]
        if "api key" in body.lower() or "create" in body.lower():
            print("  [7c] API Key page detected via body text")
            api_key_clicked = True
    
    time.sleep(5)
    safe_screenshot(page, "/home/ubuntu/alibaba-farm/step7c_apikey_page.png")
    
    # Check if we got redirected to login
    body = page.inner_text("body")[:2000]
    if "Sign In" in body or "Enter your email" in body:
        print("  [7c] ❌ API Key page redirected to login — session lost")
        safe_screenshot(page, "/home/ubuntu/alibaba-farm/step7c_login_lost.png")
        page.close()
        return {
            "email": test_email,
            "password": test_password,
            "api_key": "SESSION_LOST",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    print(f"  [7c] Current URL: {page.url}")
    print(f"  [7c] Body preview: {body[:300]}")
    
    # ─ Step 8: Create API Key (top-right button, may need scroll right) ─
    print("  [8] Create API Key...")
    time.sleep(5)
    
    # Scroll right in case button is hidden
    page.evaluate("""
        document.querySelectorAll('*').forEach(el => {
            if (el.scrollWidth > el.clientWidth) {
                el.scrollLeft = el.scrollWidth;
            }
        });
    """)
    time.sleep(2)
    
    # Use JS evaluate for speed — find and click Create API Key button
    create_clicked = False
    for wait in range(10):
        clicked = page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button, [role="button"], a');
                for (const b of btns) {
                    const txt = (b.innerText || '').trim().toLowerCase();
                    const rect = b.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        if (txt.includes('create') && (txt.includes('api') || txt.includes('key'))) {
                            b.click();
                            return txt;
                        }
                        if (txt === 'create') {
                            b.click();
                            return txt;
                        }
                    }
                }
                return null;
            }
        """)
        if clicked:
            print(f"  [8] Clicked: '{clicked}'")
            create_clicked = True
            break
        time.sleep(2)
    
    if not create_clicked:
        # Debug: list all visible buttons
        print("  [8] No Create button found. Visible buttons:")
        for b in page.query_selector_all("button, [role='button'], a"):
            try:
                txt = b.inner_text()[:80].strip()
                if b.is_visible() and txt:
                    print(f"  [8]   BTN: '{txt}'")
            except:
                pass
        safe_screenshot(page, "/home/ubuntu/alibaba-farm/step8_no_create.png")
        page.close()
        return {
            "email": test_email,
            "password": test_password,
            "api_key": "NO_CREATE_BTN",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    # ─ Step 8b: Click OK in Create API Key form → then extract key ─
    print("  [8b] Waiting for Create API Key form...")
    time.sleep(5)
    safe_screenshot(page, "/home/ubuntu/alibaba-farm/step8b_popup.png")
    
    # Click OK in the Create API Key form (Workspace + Description + Permissions)
    # Bryan: "terus bakal muncul pop up kamu pencet ok. setelah itu api key udah muncul."
    print("  [8b] Clicking OK in Create API Key form...")
    ok_clicked = False
    for wait in range(10):
        clicked = page.evaluate("""
            () => {
                // Find OK button in modal (not Cancel)
                const modals = document.querySelectorAll('[class*="modal"], [role="dialog"], [class*="dialog"]');
                for (const m of modals) {
                    const rect = m.getBoundingClientRect();
                    if (rect.width <= 0 || rect.height <= 0) continue;
                    const btns = m.querySelectorAll('button, [role="button"]');
                    for (const b of btns) {
                        const txt = (b.innerText || '').trim().toLowerCase();
                        const brect = b.getBoundingClientRect();
                        if (brect.width > 0 && brect.height > 0 && txt === 'ok') {
                            b.click();
                            return true;
                        }
                    }
                }
                // Fallback: any visible OK button
                const allBtns = document.querySelectorAll('button, [role="button"]');
                for (const b of allBtns) {
                    const txt = (b.innerText || '').trim().toLowerCase();
                    const brect = b.getBoundingClientRect();
                    if (brect.width > 0 && brect.height > 0 && txt === 'ok') {
                        b.click();
                        return true;
                    }
                }
                return false;
            }
        """)
        if clicked:
            print(f"  [8b] Clicked OK (try {wait+1})")
            ok_clicked = True
            break
        time.sleep(2)
    
    if not ok_clicked:
        print("  [8b] ❌ No OK button found in Create API Key form")
    
    # ─ Step 9: Extract API Key from "Save Your API Key" modal ─
    print("  [9] Extracting API Key...")
    api_key = None
    
    # Wait for "Save Your API Key" modal to appear with the key
    for wait in range(30):
        # Method 1: input field in modal (the "Save Your API Key" dialog)
        found = page.evaluate("""
            () => {
                // Look for input with sk- value
                const inputs = document.querySelectorAll('input');
                for (const inp of inputs) {
                    const val = inp.value || inp.getAttribute('value') || '';
                    if (val.startsWith('sk-') && val.length > 20) {
                        return val;
                    }
                }
                // Look for sk- in any element text
                const els = document.querySelectorAll('span, div, p, code, td, [class*="modal"], [role="dialog"]');
                for (const el of els) {
                    const txt = el.innerText || el.textContent || '';
                    const m = txt.match(/sk-[A-Za-z0-9._\\-]+/);
                    if (m && m[0].length > 20) {
                        return m[0];
                    }
                }
                // Look for textarea
                const textareas = document.querySelectorAll('textarea');
                for (const ta of textareas) {
                    const val = ta.value || '';
                    if (val.startsWith('sk-') && val.length > 20) {
                        return val;
                    }
                }
                return null;
            }
        """)
        
        if found:
            api_key = found
            print(f"  [9] ✅ Found API Key: {api_key[:30]}...")
            break
        
        # Method 2: click Copy button and try clipboard (only once, at wait=5)
        if wait == 5:
            page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button, [role="button"]');
                    for (const b of btns) {
                        const txt = (b.innerText || '').toLowerCase();
                        if (txt.includes('copy') || b.className.includes('copy')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            time.sleep(1)
            try:
                clip = page.evaluate("navigator.clipboard.readText()")
                if clip and clip.startswith("sk-") and len(clip) > 20:
                    api_key = clip
                    print(f"  [9] ✅ Found in clipboard: {api_key[:30]}...")
                    break
            except:
                pass
        
        if wait % 5 == 0:
            print(f"  [9] Still waiting for API key... ({wait*2}s)")
        
        time.sleep(2)
    
    safe_screenshot(page, "/home/ubuntu/alibaba-farm/step9_final.png")
    
    # NOW close the modal (only after extracting key)
    if api_key:
        page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button, [role="button"]');
                for (const b of btns) {
                    const txt = (b.innerText || '').toLowerCase();
                    const rect = b.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        if (txt.includes('ok') || txt.includes('close') || txt.includes('done') || txt.includes('confirm')) {
                            b.click();
                            return true;
                        }
                    }
                }
                return false;
            }
        """)
        print(f"  [9] Closed modal")
    else:
        print(f"  [9] ❌ No API key found after 60s")
    
    page.close()
    
    if api_key:
        print(f"  [9] ✅ API KEY: {api_key[:20]}...")
    else:
        print("  [9] ❌ No API key found")
    
    return {
        "email": test_email,
        "password": test_password,
        "api_key": api_key or "NOT_FOUND",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


def main():
    results = load_results()
    
    # ─ Proxy support ─
    # Format: host:port:user:pass  (set via FARM_PROXY env var)
    proxy_str = os.environ.get("FARM_PROXY", "")
    proxy_config = None
    if proxy_str:
        parts = proxy_str.strip().split(":")
        if len(parts) == 4:
            phost, pport, puser, ppass = parts
            proxy_config = {
                "server": f"http://{phost}:{pport}",
                "username": puser,
                "password": ppass,
            }
            print(f"Proxy: http://{phost}:{pport} (user: {puser})")
        elif len(parts) == 2:
            proxy_config = {"server": f"http://{parts[0]}:{parts[1]}"}
            print(f"Proxy: http://{parts[0]}:{parts[1]} (no auth)")
        else:
            print(f"⚠️ Invalid FARM_PROXY format: {proxy_str}")
    
    if not proxy_config:
        print("No proxy — direct VPS IP")
    
    print(f"=== Alibaba Cloud Farm ===")
    print(f"Existing accounts: {len(results)}")
    print(f"Slider solver: {'uinput' if UINPUT_AVAILABLE else 'DISABLED'}")
    print(f"Max attempts: {MAX_ATTEMPTS}")
    print()

    # Setup virtual mouse for slider solving
    mouse = setup_virtual_mouse()
    
    camoufox_kwargs = dict(
        headless=False,
        humanize=True,
        locale="en-US",
    )
    if proxy_config:
        camoufox_kwargs["proxy"] = proxy_config
    
    with Camoufox(**camoufox_kwargs) as browser:
        
        success_count = 0
        slider_count = 0
        fail_count = 0
        retries_left = MAX_ATTEMPTS * 15  # Allow up to 15x retries for slider/captcha

        while success_count < MAX_ATTEMPTS and retries_left > 0:
            retries_left -= 1
            current_attempt = success_count + slider_count + fail_count + 1
            print(f"\n{'='*50}")
            print(f"ATTEMPT {current_attempt} (target: {MAX_ATTEMPTS} success, retries left: {retries_left})")
            print(f"{'='*50}")

            result = register_one_attempt(browser)

            if result == "SLIDER":
                slider_count += 1
                print(f"  → Slider detected, retrying... (total slider: {slider_count})")
                # Exponential backoff: more sliders = longer wait
                wait = min(5 + slider_count * 3, 30)
                print(f"  → Waiting {wait}s before retry...")
                time.sleep(wait)
                continue

            if result and isinstance(result, dict):
                results.append(result)
                save_results(results)
                # Don't count SESSION_LOST as success
                if result.get("api_key") == "SESSION_LOST":
                    fail_count += 1
                    print(f"  → ❌ Session lost — API key not retrieved (total fails: {fail_count})")
                    time.sleep(random.uniform(1, 3))
                    continue
                success_count += 1
                print(f"  → ✅ SUCCESS! Total accounts: {success_count}")
                print(f"  → Email: {result['email']}")
                print(f"  → API Key: {result['api_key']}")
                continue

            fail_count += 1
            print(f"  → ❌ Failed (total fails: {fail_count})")
            time.sleep(random.uniform(1, 3))
    
    print(f"\n{'='*50}")
    print(f"DONE: {success_count} success, {slider_count} slider, {fail_count} fail")
    print(f"Total accounts in results.json: {len(results)}")
    print(f"{'='*50}")
    
    # Print full summary of all successfully farmed accounts
    if success_count > 0:
        print(f"\n{'='*50}")
        print(f"FARMED ACCOUNTS ({success_count} total):")
        print(f"{'='*50}")
        for i, r in enumerate(results, 1):
            email = r.get("email", "?")
            key = r.get("api_key", "?")
            if key == "SESSION_LOST":
                print(f"  {i}. {email} → ❌ SESSION_LOST")
            else:
                print(f"  {i}. {email}")
                print(f"     Key: {key}")
        print(f"{'='*50}")


if __name__ == "__main__":
    main()
