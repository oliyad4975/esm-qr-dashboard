import io
import os
import re
import json
import zipfile
import platform
import urllib.parse
import smtplib
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# Import ReportLab Engines for crisp PDF generation and in-memory image streaming
try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
except ImportError:
    pass

# Seamless fallback integration to ensure perfect layout parameters
try:
    import dsm_label_generator_improved as improved_engine
except ImportError:
    improved_engine = None

# -------------------------------------------------------------------------
# CONSTANTS & CONFIGURATION
# -------------------------------------------------------------------------
APP_TITLE = "Digital Standards Mark (DSM) Dashboard"
st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")

# Create systemic storage directories if they do not exist
os.makedirs("output", exist_ok=True)
os.makedirs("static", exist_ok=True)

REGISTRY_FILE = "user_registry.json"
PERMANENT_IES_LOGO_PATH = os.path.join("static", "ies_logo.png")

# -------------------------------------------------------------------------
# DISK-BASED PERSISTENT STORAGE ENGINE
# -------------------------------------------------------------------------
def load_global_registry() -> dict:
    """Loads the user database from disk. Fallbacks are injected if empty."""
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass

    # Default baseline institutional credentials if file is unreadable/missing
    registry = {}
    try:
        if "admin_creds" in st.secrets:
            sec_email = str(st.secrets["admin_creds"]["email"]).strip().lower()
            registry[sec_email] = {
                "role": "Admin",
                "name": st.secrets["admin_creds"].get("name", "Oliyad Lencho Desure"),
                "password": str(st.secrets["admin_creds"]["password"]).strip(),
                "verified": True
            }
    except Exception:
        pass

    # Hardcoded system fail-safes
    if "oliyad4975@yahoo.com" not in registry:
        registry["oliyad4975@yahoo.com"] = {
            "role": "Admin", 
            "name": "Oliyad Lencho Desure",
            "password": "AdminPassword123", 
            "verified": True
        }
    if "operator@ies.gov.et" not in registry:
        registry["operator@ies.gov.et"] = {"role": "User", "name": "Technical Officer", "password": "OperatorPassword456", "verified": True}
    if "guest@ies.gov.et" not in registry:
        registry["guest@ies.gov.et"] = {"role": "Guest", "name": "Institutional Observer", "password": "GuestPassword789", "verified": True}

    save_global_registry(registry)
    return registry

def save_global_registry(registry: dict):
    """Atomically commits user modifications directly onto disk storage."""
    try:
        with open(REGISTRY_FILE, "w") as f:
            json.dump(registry, f, indent=4)
    except Exception as e:
        st.error(f"Storage System Error: Could not save registry changes to disk: {e}")

# Initialize or synchronize session memory matrix
global_registry = load_global_registry()

if "current_user" not in st.session_state:
    st.session_state.current_user = None

if "verification_toast" not in st.session_state:
    st.session_state.verification_toast = None

if "just_verified_email" not in st.session_state:
    st.session_state.just_verified_email = None

# -------------------------------------------------------------------------
# LIVE GOOGLE SMTP TRANSACTIONAL DISPATCH ENGINE
# -------------------------------------------------------------------------
def dispatch_verification_email(recipient_email: str, recipient_name: str, verification_link: str) -> bool:
    try:
        smtp_server = st.secrets["smtp_config"]["smtp_server"]
        smtp_port = int(st.secrets["smtp_config"]["smtp_port"])
        sender_email = st.secrets["smtp_config"]["sender_email"]
        sender_password = st.secrets["smtp_config"]["sender_password"]
    except KeyError:
        st.error("Execution Aborted: Missing 'smtp_config' keys inside secrets.toml configuration layer.")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = f"Identity Access Management System <{sender_email}>"
    msg["To"] = recipient_email
    msg["Subject"] = "Verify Institutional Access Account"

    text_fallback = f"Hello {recipient_name},\n\nPlease confirm your system registration variables by navigating to:\n{verification_link}"
    html_payload = f"""
    <html>
      <body style="font-family: Arial, sans-serif; margin: 20px; color: #333333; line-height: 1.6;">
        <h2 style="color: #FF0000; border-bottom: 2px solid #FF0000; padding-bottom: 8px;">🔒 IES Verifier Identity System</h2>
        <p>Hello <strong>{recipient_name}</strong>,</p>
        <p>A new registration request has been submitted using this email parameter within our ecosystem workspace.</p>
        <p>Please confirm your identity registration parameters to activate standard system schema clearances.</p>
        <div style="margin: 30px 0;">
          <a href="{verification_link}" 
             style="background-color: #FF0000; color: #FFFFFF; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block;">
             Verify Email & Activate Account
          </a>
        </div>
        <p style="font-size: 11px; color: #777777; margin-top: 40px;">
          If the button above does not render properly, copy and paste this verification URL into your web browser address bar:<br>
          <code style="color: #FF0000;">{verification_link}</code>
        </p>
      </body>
    </html>
    """
    msg.attach(MIMEText(text_fallback, "plain"))
    msg.attach(MIMEText(html_payload, "html"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Network Dispatch Fault: Could not distribute verification email payload: {e}")
        return False

# -------------------------------------------------------------------------
# INTERCEPT URL QUERY PARAMETERS (PERSISTS ACCROSS ALL DISK INSTANCES)
# -------------------------------------------------------------------------
query_params = st.query_params
if "verify_email" in query_params and "token" in query_params:
    target_v_email = urllib.parse.unquote(query_params["verify_email"]).strip().lower()
    provided_token = query_params["token"].strip()
    expected_token = f"TOKEN_{target_v_email.split('@')[0].upper()}_SECURE"

    if provided_token == expected_token:
        # Load absolute fresh state right off the file system
        fresh_registry = load_global_registry()

        if target_v_email in fresh_registry:
            # Safely verify identity status while strictly retaining user-defined password configurations
            fresh_registry[target_v_email]["verified"] = True
            save_global_registry(fresh_registry)
            st.session_state.verification_toast = f"✅ Success! Address '{target_v_email}' is verified globally. You can now authenticate using your established password parameters."
            st.session_state.just_verified_email = target_v_email
        else:
            # Prevent silent failures or fallback mutations by flagging unrecorded routing requests
            st.session_state.verification_toast = "❌ Verification Refused: Target database record missing. Please re-execute your identity registration profile."

        st.query_params.clear()
        st.rerun()
    else:
        st.sidebar.error("❌ Link Routing Error: Security token signature is invalid or expired.")

# -------------------------------------------------------------------------
# INITIALIZE COHESIVE HISTORICAL STATISTICS METRICS
# -------------------------------------------------------------------------
if "stats_total_esm" not in st.session_state:
    st.session_state.stats_total_esm = 0
if "stats_total_eff" not in st.session_state:
    st.session_state.stats_total_eff = 0
if "stats_total_other" not in st.session_state:
    st.session_state.stats_total_other = 0

# -------------------------------------------------------------------------
# CENTRALIZED MULTI-MODE AUTHENTICATION & REGISTRATION GATEWAY
# -------------------------------------------------------------------------
def render_auth_gateway():
    if st.session_state.verification_toast:
        st.success(st.session_state.verification_toast)

    # ─── IES LOGO in header (centered above the card) ───
    ies_logo_path = os.path.join("assets", "ies_logo.png")
    if not os.path.exists(ies_logo_path):
        ies_logo_path = "ies_logo.png"

    # Center the logo using columns
    left_spacer, logo_center, right_spacer = st.columns([2, 1, 2])
    with logo_center:
        if os.path.exists(ies_logo_path):
            st.image(ies_logo_path, width=320)
        else:
            st.warning("⚠️ Logo not found. Please place 'ies_logo.png' in app folder or 'assets/' subfolder.")

    # ─── TITLE & SUBTITLE (clean, no box) ───
    st.markdown("""
    <div style='text-align: center; margin: 20px auto;'>
        <h2 style='color: #FF0000; margin: 0; font-size: 2.2rem;'>🔒 IES Verifier IAM Gateway</h2>
        <p style='color: #0066CC; font-size: 1.4rem; font-weight: bold; margin: 10px 0 0 0;'>Identity Access Management for Certification Schemes & Standard Mark Administration</p>
    </div>
    """, unsafe_allow_html=True)

    # Reload fresh registry state before handling actions
    current_live_registry = load_global_registry()

    # -------------------------------------------------------------------------
    # DIRECT POST-VERIFICATION ACCESS ROUTE (HIDES ALL INTERACTIVE TABS)
    # -------------------------------------------------------------------------
    if st.session_state.just_verified_email:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"ℹ️ **Account Verification Finished:** Access credentials for ` {st.session_state.just_verified_email} ` are active. Provide your password below to finalize your session.")

        login_password = st.text_input("Account Password", type="password", key="auth_verified_login_password").strip()

        col_verify_actions = st.columns([3, 1])
        with col_verify_actions[0]:
            if st.button("Authenticate Secure Session", type="primary", use_container_width=True, key="verified_login_submit_btn"):
                login_email = st.session_state.just_verified_email
                user_info = current_live_registry.get(login_email)

                if user_info and login_password == user_info["password"].strip():
                    st.session_state.current_user = {
                        "email": login_email,
                        "role": user_info["role"],
                        "name": user_info["name"]
                    }
                    st.session_state.just_verified_email = None
                    st.session_state.verification_toast = None
                    st.success(f"Session established successfully. Welcome, {st.session_state.current_user['name']}.")
                    st.rerun()
                else:
                    st.error("❌ Access Denied: Invalid credentials provided. Please verify your password entry.")
        with col_verify_actions[1]:
            if st.button("Cancel", use_container_width=True, key="cancel_verified_view_btn"):
                st.session_state.just_verified_email = None
                st.session_state.verification_toast = None
                st.rerun()
    else:
        # Standard workflow tab matrix layout
        auth_tab1, auth_tab2, auth_tab3 = st.tabs(["Existing User Sign-In", "New User Registration", "🔑 Recovery & Password Reset"])

        with auth_tab1:
            st.markdown("<br>", unsafe_allow_html=True)
            login_email = st.text_input("Institutional Email Address", key="auth_login_email").strip().lower()
            login_password = st.text_input("Account Password", type="password", key="auth_login_password").strip()

            if st.button("Authenticate Secure Session", type="primary", use_container_width=True, key="login_submit_btn"):
                if not login_email or not login_password:
                    st.error("❌ Identification Required: Both email address and password must be provided.")
                elif login_email in current_live_registry:
                    user_info = current_live_registry[login_email]
                    if not user_info.get("verified", False):
                        st.error("❌ Access Blocked: This email identity is unverified! Please execute your pending inbox validation routing link.")
                    elif login_password == user_info["password"].strip():
                        st.session_state.current_user = {
                            "email": login_email,
                            "role": user_info["role"],
                            "name": user_info["name"]
                        }
                        st.session_state.verification_toast = None
                        st.success(f"Session established successfully. Welcome, {st.session_state.current_user['name']}.")
                        st.rerun()
                    else:
                        st.error("❌ Access Denied: Invalid credentials provided. Please verify your password entry.")
                else:
                    st.error("❌ Authentication Refused: The provided email is not registered within this ecosystem database.")

        with auth_tab2:
            st.markdown("<br>", unsafe_allow_html=True)
            reg_name = st.text_input("Full Name", key="auth_reg_name").strip()
            reg_email = st.text_input("Account Email Address", key="auth_reg_email").strip().lower()
            reg_password = st.text_input("Choose Account Password", type="password", key="auth_reg_password").strip()
            reg_intent = st.selectbox("Requested Institutional Access Level", ["Guest", "Expert/User"], key="auth_reg_intent")

            st.caption("ℹ️ Note: Registration requests automatically default to 'Guest' or 'User' privileges pending Admin evaluation.")

            if st.button("Submit Registration Profile", type="secondary", use_container_width=True, key="reg_submit_btn"):
                if not reg_name or not reg_email or not reg_password:
                    st.error("❌ Incomplete Profile: Name, email credentials, and a secure password must be completed.")
                elif "@" not in reg_email:
                    st.error("❌ Syntax Error: Please provide a valid email structure (e.g., identity@domain.com).")
                elif reg_email in current_live_registry:
                    st.warning("⚠️ Record Exists: This email is already present in the user base register. Proceed to Sign-In.")
                else:
                    assigned_role = "User" if "Expert/User" in reg_intent else "Guest"
                    current_live_registry[reg_email] = {
                        "role": assigned_role,
                        "name": reg_name,
                        "password": reg_password,
                        "verified": False
                    }
                    save_global_registry(current_live_registry)

                    token_hash = f"TOKEN_{reg_email.split('@')[0].upper()}_SECURE"
                    encoded_email = urllib.parse.quote(reg_email)

                    # Dynamic URL generation
                    verification_url = f"http://localhost:8501/?verify_email={encoded_email}&token={token_hash}"

                    with st.spinner("Dispatching secure validation token payload to inbox..."):
                        success = dispatch_verification_email(reg_email, reg_name, verification_url)

                    if success:
                        st.success(f"🎉 Verification pipeline activated! An authentication routing link has been distributed to {reg_email}.")
                        st.info("📨 Check your mailbox inbox or spam folder to validate and finish establishing access rules.")

        with auth_tab3:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("🥇 **Self-Service Out-of-Session Recovery**")
            recovery_email = st.text_input("Enter Registered Account Email Address", key="auth_recovery_email").strip().lower()
            new_recovery_pwd = st.text_input("Provide New Target Password String", type="password", key="auth_recovery_new_pwd").strip()

            if st.button("Authorize Structural Password Rewrite", type="secondary", use_container_width=True):
                if not recovery_email or not new_recovery_pwd:
                    st.error("❌ Profile Alteration Refused: Complete all input forms to establish modifications.")
                elif recovery_email in current_live_registry:
                    current_live_registry[recovery_email]["password"] = new_recovery_pwd
                    save_global_registry(current_live_registry)
                    st.success("🎉 Passphrase altered successfully within authorization registries! Switch back to 'Existing User Sign-In' to sign in.")
                else:
                    st.error("❌ Identity Match Failure: Target entry context does not exist.")

    st.markdown("</div>", unsafe_allow_html=True)

# Halt downstream processing if context is unauthenticated
if st.session_state.current_user is None:
    render_auth_gateway()
    st.stop()

USER_ROLE = st.session_state.current_user["role"]
IS_ADMIN = (USER_ROLE == "Admin")
IS_USER = (USER_ROLE == "User")
IS_GUEST = (USER_ROLE == "Guest")

# -------------------------------------------------------------------------
# RE-ENGINEERED COMPLIANCE LABEL TEMPLATE (WITH MARGIN ADJUSTMENTS)
# -------------------------------------------------------------------------
def render_compliance_label(qr_img, logo_img, company, product, standard, client_id, width, height, font_sz):
    """
    Renders a compliance label with:
    1. QR code on left — actual data modules define the height
    2. Text + logo in a BOX on right — matches actual QR data height
    3. All text same font size, single line each
    4. Logo at 85% fill
    """
    canvas_w = int(width) if width else 1200
    canvas_h = int(height) if height else 600

    img = Image.new("RGB", (canvas_w, canvas_h), color="white")
    draw = ImageDraw.Draw(img)

    # ─── STEP 1: FIND ACTUAL QR DATA BOUNDS (crop quiet zone) ───
    if qr_img:
        qr_gray = qr_img.convert("L")
        qr_array = list(qr_gray.getdata())
        qr_w, qr_h = qr_gray.size

        # Find topmost black pixel
        top_black = 0
        for y in range(qr_h):
            row_black = False
            for x in range(qr_w):
                if qr_array[y * qr_w + x] < 128:
                    row_black = True
                    break
            if row_black:
                top_black = y
                break

        # Find bottommost black pixel
        bottom_black = qr_h - 1
        for y in range(qr_h - 1, -1, -1):
            row_black = False
            for x in range(qr_w):
                if qr_array[y * qr_w + x] < 128:
                    row_black = True
                    break
            if row_black:
                bottom_black = y
                break

        # Find leftmost black pixel
        left_black = 0
        for x in range(qr_w):
            col_black = False
            for y in range(qr_h):
                if qr_array[y * qr_w + x] < 128:
                    col_black = True
                    break
            if col_black:
                left_black = x
                break

        # Find rightmost black pixel
        right_black = qr_w - 1
        for x in range(qr_w - 1, -1, -1):
            col_black = False
            for y in range(qr_h):
                if qr_array[y * qr_w + x] < 128:
                    col_black = True
                    break
            if col_black:
                right_black = x
                break

        # Actual QR data dimensions (without quiet zone)
        data_w = right_black - left_black + 1
        data_h = bottom_black - top_black + 1
        data_size = max(data_w, data_h)
    else:
        data_size = int(canvas_h * 0.85)
        top_black = 0
        left_black = 0

    # ─── STEP 2: SHARED VERTICAL SPAN = ACTUAL QR DATA HEIGHT ───
    margin = int(canvas_h * 0.025)
    shared_h = data_size  # Use actual QR data height, not image height
    shared_top = (canvas_h - shared_h) // 2  # Center vertically
    shared_bottom = shared_top + shared_h

    # ─── STEP 3: QR CODE — crop to actual data, resize to shared_h ───
    qr_x = margin
    qr_y = shared_top

    if qr_img:
        # Crop to actual data bounds
        qr_cropped = qr_img.crop((left_black, top_black, right_black + 1, bottom_black + 1))
        qr_resized = qr_cropped.resize((shared_h, shared_h), Image.Resampling.LANCZOS)
        img.paste(qr_resized, (qr_x, qr_y))

    # ─── STEP 4: BOX — same height as actual QR data ───
    gap = int(canvas_h * 0.04)
    box_x = qr_x + shared_h + gap
    box_w = canvas_w - box_x - margin
    box_h = shared_h  # EXACT same as actual QR data height
    box_y = shared_top

    # Inner content area
    inner_pad = int(box_h * 0.03)
    content_x = box_x + inner_pad
    content_w = box_w - (2 * inner_pad)
    content_center_x = content_x + (content_w // 2)
    max_text_w = int(content_w * 0.95)

    content_top = box_y + inner_pad
    content_bottom = box_y + box_h - inner_pad
    content_h = content_bottom - content_top

    # ─── FONT SETUP ───
    font_name = "BERNHC.TTF"
    system_font_paths = [
        font_name,
        os.path.join("C:\\", "Windows", "Fonts", font_name),
        os.path.join("C:\\", "Windows", "Fonts", "Bernard MT Condensed.ttf"),
        os.path.join("/Library/Fonts", font_name),
        os.path.join("~/.fonts", font_name)
    ]

    target_size = int(font_sz) if font_sz else 26
    font_loaded = None
    for path in system_font_paths:
        try:
            font_loaded = ImageFont.truetype(os.path.expanduser(path), target_size)
            break
        except Exception:
            continue
    if not font_loaded:
        try:
            font_loaded = ImageFont.load_default()
        except Exception:
            font_loaded = None

    # ─── COLLECT ALL TEXT LINES ───
    all_lines = []
    if company and str(company).lower() != "nan":
        all_lines.append(str(company).upper().strip())
    if product and str(product).lower() != "nan":
        all_lines.append(str(product).upper().strip())
    if standard and str(standard).lower() != "nan":
        clean_std = re.sub(r"^STANDARD\s+R/NO:\s*", "", str(standard), flags=re.IGNORECASE).strip().upper()
        if clean_std:
            all_lines.append(clean_std)
    if client_id and str(client_id).lower() != "nan":
        clean_client = re.sub(r"^CLIENT\s+CODE:\s*", "", str(client_id), flags=re.IGNORECASE).strip().upper()
        if clean_client:
            all_lines.append(clean_client)

    if not all_lines:
        all_lines = ["REGISTERED CLIENT PLC", "PRODUCT SPECIFICATION", "CES / ISO STANDARD", "BATCH IDENTIFIER"]

    # ─── FIND FONT SIZE — everything must fit in content_h ───
    line_gap = int(content_h * 0.015)
    min_logo_h = int(content_h * 0.25)

    lo, hi = 8, int(content_h * 0.13)
    best_font = None
    best_line_h = 0
    best_size = 8

    while lo <= hi:
        mid = (lo + hi) // 2
        try:
            test_font = ImageFont.truetype(font_loaded.path, mid) if hasattr(font_loaded, 'path') else font_loaded
        except:
            test_font = font_loaded

        all_fit = True
        for line in all_lines:
            bbox = draw.textbbox((0, 0), line, font=test_font)
            if (bbox[2] - bbox[0]) > max_text_w:
                all_fit = False
                break

        if not all_fit:
            hi = mid - 1
            continue

        bbox = draw.textbbox((0, 0), "Ay", font=test_font)
        line_h = bbox[3] - bbox[1]
        total_text_h = len(all_lines) * line_h + (len(all_lines) - 1) * line_gap

        if total_text_h + min_logo_h <= content_h:
            best_size = mid
            best_font = test_font
            best_line_h = line_h
            lo = mid + 1
        else:
            hi = mid - 1

    # Use NEXT LOWER font size (reduce by one step from best fit)
    if best_font and best_size > 9:
        next_lower = max(8, best_size - 2)  # go down ~2 points
        try:
            best_font = ImageFont.truetype(font_loaded.path, next_lower) if hasattr(font_loaded, 'path') else ImageFont.truetype("arial.ttf", next_lower)
            bbox = draw.textbbox((0, 0), "Ay", font=best_font)
            best_line_h = bbox[3] - bbox[1]
            best_size = next_lower
        except:
            pass

    if best_font is None:
        best_font = font_loaded
        bbox = draw.textbbox((0, 0), "Ay", font=best_font)
        best_line_h = bbox[3] - bbox[1]

    # ─── POSITION TEXT inside box ───
    total_text_h = len(all_lines) * best_line_h + (len(all_lines) - 1) * line_gap

    # Company at content_top
    company_y = content_top + best_line_h // 2
    if best_font:
        draw.text((content_center_x, company_y), all_lines[0], fill="black", anchor="mm", font=best_font)

    # Metadata at content_bottom
    meta_lines = all_lines[1:]
    if meta_lines:
        meta_total_h = len(meta_lines) * best_line_h + (len(meta_lines) - 1) * line_gap
        meta_start_y = content_bottom - meta_total_h + best_line_h // 2
        for i, line in enumerate(meta_lines):
            y = meta_start_y + i * (best_line_h + line_gap)
            if best_font:
                draw.text((content_center_x, y), line, fill="black", anchor="mm", font=best_font)

    # ─── LOGO — centered in middle, 85% fill ───
    logo_top = company_y + best_line_h // 2 + int(content_h * 0.02)
    if meta_lines:
        logo_bottom = meta_start_y - best_line_h // 2 - int(content_h * 0.02)
    else:
        logo_bottom = content_bottom - int(content_h * 0.02)

    avail_logo_h = logo_bottom - logo_top
    avail_logo_w = content_w

    if logo_img and avail_logo_h > 15 and avail_logo_w > 15:
        lr = logo_img.width / logo_img.height
        max_lw = int(avail_logo_w * 0.95)
        max_lh = int(avail_logo_h * 0.95)

        if lr > (max_lw / max_lh):
            lw = max_lw
            lh = int(lw / lr)
        else:
            lh = max_lh
            lw = int(lh * lr)

        lw = min(lw, avail_logo_w)
        lh = min(lh, avail_logo_h)

        lx = content_x + (avail_logo_w - lw) // 2
        ly = logo_top + (avail_logo_h - lh) // 2

        logo_resized = logo_img.resize((lw, lh), Image.Resampling.LANCZOS)

        if logo_resized.mode in ('RGBA', 'LA') or (logo_resized.mode == 'P' and 'transparency' in logo_resized.info):
            logo_rgba = logo_resized.convert("RGBA")
            background = Image.new("RGBA", logo_rgba.size, (255, 255, 255, 255))
            logo_final = Image.alpha_composite(background, logo_rgba).convert("RGB")
        else:
            logo_final = logo_resized.convert("RGB")

        img.paste(logo_final, (lx, ly))

    # ─── BORDER FRAME RECTANGLE around entire label ───
    frame_border = max(2, int(canvas_h * 0.008))
    draw.rectangle(
        [(0, 0), (canvas_w - 1, canvas_h - 1)],
        outline=(0, 0, 0),
        width=frame_border
    )

    return img

# -------------------------------------------------------------------------
# INITIAL THEME CONTROL STATES
# -------------------------------------------------------------------------
text_header_color = "#FF0000"
ui_bg_color = "#FFFFFF"
ui_sidebar_bg_color = "#F0F2F6"

chosen_theme = st.session_state.get("top_right_layout_theme", "Default Layout")


# Apply theme
if "dashboard_theme" not in st.session_state:
    st.session_state.dashboard_theme = "System"

# Apply theme with proper contrast
if st.session_state.dashboard_theme == "Dark":
    st.markdown("""
    <style>
    /* ================================================================
       DARK MODE - COMPREHENSIVE CONTRAST FIXES
       ================================================================ */

    /* Main app background */
    .stApp { background-color: #0E1117 !important; }

    /* ALL text elements - force light color */
    .stApp, .stMarkdown, p, h1, h2, h3, h4, h5, h6, 
    label, .stTextInput label, .stSelectbox label, 
    .stFileUploader label, .stSlider label, span, div {
        color: #FAFAFA !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #1A1D24 !important; }
    [data-testid="stSidebar"] * {
        color: #FAFAFA !important;
    }

    /* ================================================================
       INPUT FIELDS (text boxes, passwords, etc.)
       ================================================================ */
    .stTextInput input, .stTextInput textarea, 
    .stNumberInput input, .stDateInput input,
    div[data-baseweb="input"] input, 
    div[data-baseweb="textarea"] textarea,
    input[type="text"], input[type="password"] {
        background-color: #262730 !important;
        color: #FAFAFA !important;
        border-color: #4A4A4A !important;
        -webkit-text-fill-color: #FAFAFA !important;
    }

    /* ================================================================
       SELECT BOXES / DROPDOWNS
       ================================================================ */
    .stSelectbox div[data-baseweb="select"] > div,
    div[data-baseweb="select"] > div,
    div[data-baseweb="select"] input {
        background-color: #262730 !important;
        color: #FAFAFA !important;
        border-color: #4A4A4A !important;
        -webkit-text-fill-color: #FAFAFA !important;
    }

    /* ================================================================
       FILE UPLOADER - Fix white boxes with invisible text
       ================================================================ */
    .stFileUploader > section,
    .stFileUploader > section > div,
    .stFileUploader [data-testid="stFileUploaderDropzone"] {
        background-color: #262730 !important;
        border: 2px dashed #4A4A4A !important;
    }
    .stFileUploader [data-testid="stFileUploaderDropzone"] * {
        color: #FAFAFA !important;
    }
    .stFileUploader [data-testid="stFileUploaderDropzone"] button {
        background-color: #FF4B4B !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    .stFileUploader [data-testid="stFileUploaderDropzone"] button:hover {
        background-color: #FF6B6B !important;
    }
    .stFileUploader [data-testid="stFileUploaderDropzone"] svg {
        fill: #FAFAFA !important;
        color: #FAFAFA !important;
    }

    /* ================================================================
       BUTTONS - All button types including popover, upload, etc.
       ================================================================ */
    /* Base button styling */
    button[kind="secondary"],
    button[kind="tertiary"],
    [data-testid="stBaseButton-secondary"],
    [data-testid="stBaseButton-tertiary"],
    .stButton > button {
        background-color: #262730 !important;
        color: #FAFAFA !important;
        border: 1px solid #4A4A4A !important;
    }
    button[kind="secondary"]:hover,
    button[kind="tertiary"]:hover,
    [data-testid="stBaseButton-secondary"]:hover,
    [data-testid="stBaseButton-tertiary"]:hover,
    .stButton > button:hover {
        background-color: #3A3A4A !important;
        border-color: #6A6A7A !important;
    }

    /* Primary buttons */
    button[kind="primary"],
    [data-testid="stBaseButton-primary"],
    .stButton > button[kind="primary"] {
        background-color: #FF4B4B !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        background-color: #FF6B6B !important;
    }

    /* Popover trigger button (the user profile button) */
    [data-testid="stPopover"] > button,
    [data-testid="stPopoverTrigger"] > button {
        background-color: #262730 !important;
        color: #FAFAFA !important;
        border: 1px solid #4A4A4A !important;
    }
    [data-testid="stPopover"] > button:hover,
    [data-testid="stPopoverTrigger"] > button:hover {
        background-color: #3A3A4A !important;
        border-color: #6A6A7A !important;
    }
    /* Ensure icon inside popover button is visible */
    [data-testid="stPopover"] > button svg,
    [data-testid="stPopoverTrigger"] > button svg,
    [data-testid="stPopover"] > button span,
    [data-testid="stPopoverTrigger"] > button span {
        fill: #FAFAFA !important;
        color: #FAFAFA !important;
    }

    /* ================================================================
       SLIDERS
       ================================================================ */
    .stSlider div[data-baseweb="slider"] div,
    .stSlider label {
        color: #FAFAFA !important;
    }

    /* ================================================================
       DATAFRAMES AND TABLES
       ================================================================ */
    .stDataFrame, .stTable,
    .stDataFrame td, .stDataFrame th,
    .stTable td, .stTable th {
        color: #FAFAFA !important;
        background-color: #1A1D24 !important;
    }

    /* ================================================================
       POPOVER DROPDOWN MENU
       ================================================================ */
    [data-testid="stPopover"] > div[role="dialog"],
    [data-testid="stPopover"] > div[data-popover] {
        background-color: #1E1E2E !important;
        border: 1px solid #4A4A4A !important;
    }
    [data-testid="stPopover"] > div[role="dialog"] *,
    [data-testid="stPopover"] > div[data-popover] * {
        color: #FAFAFA !important;
    }

    /* ================================================================
       TABS
       ================================================================ */
    button[data-baseweb="tab"] {
        color: #AAAAAA !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #FAFAFA !important;
        border-bottom-color: #FF4B4B !important;
    }

    /* ================================================================
       METRICS
       ================================================================ */
    [data-testid="stMetricValue"] {
        color: #FAFAFA !important;
    }
    [data-testid="stMetricLabel"] {
        color: #AAAAAA !important;
    }

    /* ================================================================
       ALERTS (success/error/warning/info)
       ================================================================ */
    .stAlert, [data-testid="stAlert"] {
        color: #FAFAFA !important;
    }
    .stAlert > div, [data-testid="stAlert"] > div {
        color: #FAFAFA !important;
    }

    /* ================================================================
       CODE BLOCKS
       ================================================================ */
    code, pre code {
        background-color: #262730 !important;
        color: #FF4B4B !important;
    }

    /* ================================================================
       HORIZONTAL RULES
       ================================================================ */
    hr {
        border-color: #4A4A4A !important;
    }

    /* ================================================================
       TOGGLES / SWITCHES
       ================================================================ */
    div[data-testid="stToggle"] label,
    div[data-testid="stToggle"] span {
        color: #FAFAFA !important;
    }

    /* ================================================================
       CHECKBOXES AND RADIO BUTTONS
       ================================================================ */
    .stCheckbox label, .stRadio label,
    .stCheckbox span, .stRadio span {
        color: #FAFAFA !important;
    }

    /* ================================================================
       CAPTIONS
       ================================================================ */
    .stCaption, small {
        color: #AAAAAA !important;
    }

    /* ================================================================
       LINKS
       ================================================================ */
    a, a:visited {
        color: #4BB4FF !important;
    }
    a:hover {
        color: #6BC4FF !important;
    }

    /* ================================================================
       STREAMLIT SPECIFIC COMPONENTS
       ================================================================ */
    /* Ensure all Streamlit-generated text is visible */
    [data-testid] {
        color: #FAFAFA;
    }
    /* But don't override inputs that already have specific styling */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] input {
        color: #FAFAFA !important;
        -webkit-text-fill-color: #FAFAFA !important;
    }
    </style>
    """, unsafe_allow_html=True)
elif st.session_state.dashboard_theme == "Light":
    st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #F0F2F6 !important; }
    .stApp, .stMarkdown, p, h1, h2, h3, h4, h5, h6, label { color: #000000 !important; }
    </style>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------------------
# USER INTERFACE SIDEBAR CONTROL PANEL
# -------------------------------------------------------------------------

# ─── USER PROFILE POPOVER (moved to top of sidebar) ───
with st.sidebar.popover(f"👤 {USER_ROLE}", use_container_width=True):
    st.markdown(
        f"""
        <div style='padding: 2px 4px; margin-bottom: 8px; border-bottom: 1px solid #EEEEEE;'>
            <p style='margin:0; font-size:0.8rem; color:#666666;'>Authenticated Active Session:</p>
            <code style='color:#28A745; font-size:0.85rem;'>{st.session_state.current_user['email']}</code>
        </div>
        """, 
        unsafe_allow_html=True
    )

    if st.button("🚪 Logout", type="secondary", key="logout_execution_handler", use_container_width=True):
        st.session_state.current_user = None
        st.rerun()

    st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:0.85rem; font-weight:bold; margin:4px 0;'>🔄 Reset password parameters:</p>", unsafe_allow_html=True)
    old_sidebar_pwd = st.text_input("Current Password", type="password", key="hdr_old_pwd_field").strip()
    new_sidebar_pwd = st.text_input("New Password", type="password", key="hdr_new_pwd_field").strip()

    if st.button("Commit Reset", use_container_width=True, key="hdr_pwd_commit_action_btn"):
        current_active_email = st.session_state.current_user["email"]
        live_reg = load_global_registry()
        real_registered_pwd = live_reg[current_active_email]["password"].strip()

        if not old_sidebar_pwd or not new_sidebar_pwd:
            st.error("Input parameters missing.")
        elif old_sidebar_pwd != real_registered_pwd:
            st.error("Verification Failure: Current mismatch.")
        else:
            live_reg[current_active_email]["password"] = new_sidebar_pwd
            save_global_registry(live_reg)
            st.success("Credentials updated successfully.")

    st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:0.85rem; font-weight:bold; margin:4px 0; color: inherit;'>🎨 Theme Mode:</p>", unsafe_allow_html=True)

    current_theme = st.session_state.get("dashboard_theme", "System")

    tcol1, tcol2, tcol3 = st.columns([1, 1, 1])

    with tcol1:
        is_active = current_theme == "System"
        btn_type = "primary" if is_active else "secondary"
        if st.button(f"🖥️ System", type=btn_type, use_container_width=True, key="theme_system"):
            st.session_state.dashboard_theme = "System"
            st.rerun()
    with tcol2:
        is_active = current_theme == "Light"
        btn_type = "primary" if is_active else "secondary"
        if st.button(f"☀️ Light", type=btn_type, use_container_width=True, key="theme_light"):
            st.session_state.dashboard_theme = "Light"
            st.rerun()
    with tcol3:
        is_active = current_theme == "Dark"
        btn_type = "primary" if is_active else "secondary"
        if st.button(f"🌙 Dark", type=btn_type, use_container_width=True, key="theme_dark"):
            st.session_state.dashboard_theme = "Dark"
            st.rerun()

    if not IS_GUEST and IS_ADMIN:
        st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
        theme_mode = st.selectbox("Workspace Base Viewport Layout", ["Default Layout", "Custom Color Palette Mode"], key="top_right_layout_theme")
        if theme_mode != chosen_theme:
            st.rerun()

st.sidebar.markdown("<br>", unsafe_allow_html=True)

if os.path.exists(PERMANENT_IES_LOGO_PATH):
    try:
        ies_fixed_logo = Image.open(PERMANENT_IES_LOGO_PATH)
        st.sidebar.image(ies_fixed_logo, use_container_width=True)
    except Exception:
        pass

if chosen_theme == "Custom Color Palette Mode" and IS_ADMIN:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎨 Custom Dynamic Canvas Colors")
    text_header_color = st.sidebar.color_picker("Main Title Text Color", "#FF0000")
    ui_bg_color = st.sidebar.color_picker("App Workspace Background Color", "#FFFFFF")
    ui_sidebar_bg_color = st.sidebar.color_picker("Sidebar Left Panel Color", "#F0F2F6")

    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {ui_bg_color} !important; }}
        [data-testid="stSidebar"] {{ background-color: {ui_sidebar_bg_color} !important; }}
        </style>
        """,
        unsafe_allow_html=True
    )

st.sidebar.subheader("Asset Repositories Upload")

sb_logo_list = st.sidebar.file_uploader(
    "Upload Institutional Logos (Select Multiple: ESM LOGO, EFF LOGO)", 
    type=["png", "jpg", "jpeg"], 
    accept_multiple_files=True,
    key="app_logo_uploader",
    disabled=IS_GUEST
)

sb_qr_list = st.sidebar.file_uploader(
    "Upload Dynamic Target QR Codes (Select All / Drop Multiple)", 
    type=["png", "jpg", "jpeg"], 
    accept_multiple_files=True,
    key="app_qr_uploader",
    disabled=IS_GUEST
)

st.sidebar.markdown("---")
st.sidebar.subheader("Layout Optimization Adjustments")

ui_width = st.sidebar.slider("Label Width (px)", 800, 2400, 1200, step=100, key="sidebar_label_width_slider", disabled=IS_GUEST)
ui_height = st.sidebar.slider("Label Height (px)", 400, 1200, 600, step=50, key="sidebar_label_height_slider", disabled=IS_GUEST)
ui_font_sz = st.sidebar.slider("Metadata Font Scale", 12, 48, 24, step=2, key="sidebar_font_size_slider", disabled=IS_GUEST)

# -------------------------------------------------------------------------
# TOP LEVEL STATISTICS METRICS INFRASTRUCTURE
# -------------------------------------------------------------------------
total_labels = st.session_state.stats_total_esm + st.session_state.stats_total_eff + st.session_state.stats_total_other
esm_ratio = (st.session_state.stats_total_esm / total_labels * 100) if total_labels > 0 else 0.0
eff_ratio = (st.session_state.stats_total_eff / total_labels * 100) if total_labels > 0 else 0.0

stat_col1, stat_col2, stat_col3, stat_col4, stat_col5 = st.columns(5)
with stat_col1:
    st.metric("Total Labels Generated", f"{total_labels}")
with stat_col2:
    st.metric("ESM Marks Created", f"{st.session_state.stats_total_esm}")
with stat_col3:
    st.metric("EFF Marks Created", f"{st.session_state.stats_total_eff}")
with stat_col4:
    st.metric("ESM Distribution Ratio", f"{esm_ratio:.1f}%")
with stat_col5:
    st.metric("EFF Distribution Ratio", f"{eff_ratio:.1f}%")

st.markdown("<hr style='margin-top: 0.5rem; margin-bottom: 1rem;'>", unsafe_allow_html=True)

# -------------------------------------------------------------------------
# CENTRAL WORKSPACE ENVIRONMENT
# -------------------------------------------------------------------------
st.markdown(f'<h1 style="color:{text_header_color}; font-size:1.9rem; margin-bottom:0px; margin-top:0px; padding-top:0px; line-height: 1.2;">ETHIOPIAN STANDARD MARK UNIQUE CLIENT ID GENERATOR</h1>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

available_tabs = ["Manual Processing Pipeline", "Automated Bulk Processing Pipeline"]
if IS_ADMIN:
    available_tabs.append("🛡️ Admin Identity Control Panel")

tabs_objects = st.tabs(available_tabs)

if "preview_image_bytes" not in st.session_state:
    st.session_state.preview_image_bytes = None

logo_cache = {}
if sb_logo_list:
    for logo_f in sb_logo_list:
        norm_name = os.path.splitext(logo_f.name.strip().lower())[0].replace(" logo", "").strip()
        logo_cache[norm_name] = logo_f

# =========================================================================
# TAB 1: MANUAL PROCESSING PIPELINE
# =========================================================================
with tabs_objects[0]:
    st.subheader("Mark License Metadata Form Structure")
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        sb_company = st.text_input("Registered Company / Trading Entity Name", value="", disabled=IS_GUEST)
        sb_product = st.text_input("Product Classification Descriptor", value="", disabled=IS_GUEST)
    with row1_col2:
        sb_standard = st.text_input("Standard reference No.", value="", disabled=IS_GUEST)
        sb_client = st.text_input("Client Identifier Reference (Enforced Batch ID Code)", value="", disabled=IS_GUEST)

    manual_mark_type = st.selectbox("Assign Manual Mockup Logo Type", ["ESM", "EFF", "Other"], key="manual_mark_type_dropdown", disabled=IS_GUEST)

    st.markdown("---")
    col_view, col_actions = st.columns([2, 1])

    with col_view:
        st.subheader("Live Composite Label Verification Preview")

        if IS_GUEST:
            st.warning("🔒 View-Only Mode Active: Interactive processing pipelines are locked.")
        else:
            if st.button("Generate Preview", type="secondary", key="manual_preview_btn"):
                if not sb_client.strip():
                    st.error("❌ Input Error: Client Identifier Reference cannot be empty for verification pipelines.")
                elif sb_logo_list and sb_qr_list:
                    expected_qr_filename = f"{sb_client.strip()}-qr-code.png".lower()
                    target_logo_key = manual_mark_type.strip().lower()

                    matched_qr_file = None
                    for uploaded_file in sb_qr_list:
                        if uploaded_file.name.strip().lower() == expected_qr_filename:
                            matched_qr_file = uploaded_file
                            break

                    matched_logo_file = logo_cache.get(target_logo_key)

                    if not matched_qr_file:
                        st.error(f"❌ Security Block: Matching QR File Not Found! Include file named: **{sb_client.strip()}-qr-code.png**")
                        st.session_state.preview_image_bytes = None
                    elif not matched_logo_file:
                        st.error(f"❌ Security Block: Matching Logo Profile Missing! Upload **{manual_mark_type} LOGO.png**")
                        st.session_state.preview_image_bytes = None
                    else:
                        try:
                            logo = Image.open(matched_logo_file)
                            qr = Image.open(matched_qr_file)

                            preview = render_compliance_label(qr, logo, sb_company, sb_product, sb_standard, sb_client, ui_width, ui_height, ui_font_sz)
                            st.image(preview, caption=f"Label Verification Preview ({manual_mark_type} Scheme Layout)", use_container_width=True)

                            buf = io.BytesIO()
                            preview.save(buf, format="PNG")
                            st.session_state.preview_image_bytes = buf.getvalue()

                            if manual_mark_type == "ESM":
                                st.session_state.stats_total_esm += 1
                            elif manual_mark_type == "EFF":
                                st.session_state.stats_total_eff += 1
                            else:
                                st.session_state.stats_total_other += 1

                            st.success("Symmetric spaces balanced perfectly inside a borderless layout footprint.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Preview generation failed: {e}")
                else:
                    st.warning("Please upload institutional logos and selection QR configurations in the left sidebar workspace repository.")

    with col_actions:
        st.subheader("Institutional Actions")
        st.info("Ensure layouts conform perfectly with national certification schemes rules before authorizing exports.")

        if not IS_GUEST and st.session_state.preview_image_bytes is not None:
            st.download_button(
                label="Download Certified Label Image (PNG)",
                data=st.session_state.preview_image_bytes,
                file_name=f"DSM_Label_{sb_client.strip() if sb_client.strip() else 'export'}.png",
                mime="image/png",
                key="dsm_png_download_handler_btn",
                use_container_width=True
            )
        else:
            st.button("Download Certified Label Image (PNG)", disabled=True, use_container_width=True)

        st.markdown(" ")

        if not IS_GUEST and st.button("Compile & Export Production Vector PDF", type="primary", key="manual_export_pdf_btn", use_container_width=True):
            if not sb_client.strip():
                st.error("❌ Input Error: Client Identifier Reference is required.")
            elif sb_logo_list and sb_qr_list:
                expected_qr_filename = f"{sb_client.strip()}-qr-code.png".lower()
                target_logo_key = manual_mark_type.strip().lower()

                matched_qr_file = None
                for uploaded_file in sb_qr_list:
                    if uploaded_file.name.strip().lower() == expected_qr_filename:
                        matched_qr_file = uploaded_file
                        break

                matched_logo_file = logo_cache.get(target_logo_key)

                if not matched_qr_file or not matched_logo_file:
                    st.error("❌ Action Blocked: Resolve QR asset and Logo naming compliance.")
                else:
                    try:
                        output_pdf_path = "output/Production_DSM_Label.pdf"
                        data_payload = {'client_name': sb_company, 'product_desc': sb_product, 'standard_code': sb_standard, 'batch_id': sb_client}

                        if improved_engine is not None:
                            with open("static/temp_qr.png", "wb") as f:
                                f.write(matched_qr_file.getbuffer())
                            with open("static/temp_logo.png", "wb") as f:
                                f.write(matched_logo_file.getbuffer())

                            improved_engine.generate_dsm_label(output_pdf_path, "static/temp_qr.png", "static/temp_logo.png", data_payload)

                            with open(output_pdf_path, "rb") as pdf_file:
                                st.download_button(label="Download Certified Vector PDF Document", data=pdf_file.read(), file_name=f"Production_DSM_Label_{sb_client.strip()}.pdf", mime="application/pdf", key="dsm_pdf_download_handler_btn", use_container_width=True)
                            st.success("Vector PDF Compiled Successfully.")
                    except Exception as e:
                        st.error(f"Production compilation failed: {e}")

# =========================================================================
# TAB 2: AUTOMATED BULK PROCESSING PIPELINE
# =========================================================================
with tabs_objects[1]:
    st.subheader("Bulk Registry Import Interface")

    if IS_GUEST:
        st.warning("🔒 View-Only Mode Active: Batch modification operations are completely disabled.")
    else:
        excel_file = st.file_uploader("Upload 5-Column Master Certification Excel Sheet", type=["xlsx"], key="bulk_pipeline_excel_uploader")

        if excel_file is not None:
            try:
                df = pd.read_excel(excel_file)
                st.dataframe(df, use_container_width=True)

                required_cols = ['Company Name', 'Product Descriptor', 'Standard Code', 'Client Identifier', 'Mark type']
                missing_cols = [col for col in required_cols if col not in df.columns]

                if missing_cols:
                    st.error(f"Validation Error: Missing tracking columns: {missing_cols}")
                else:
                    st.success(f"System validation passed. Detected {len(df)} registry items.")

                    btn_col1, btn_col2, btn_col3 = st.columns([1.5, 1.5, 4])

                    with btn_col1:
                        execute_bulk = st.button("Execute Bulk Label Generation", type="primary", use_container_width=True, key="bulk_execute_generation_btn")

                    with btn_col2:
                        preview_bulk = st.button("Preview First Batch Row", type="secondary", use_container_width=True, key="bulk_preview_first_row_btn")

                    if preview_bulk:
                        if not sb_logo_list or not sb_qr_list:
                            st.error("❌ Preview Blocked: Please upload your asset repository images (Logos and QR codes) into the sidebar first.")
                        else:
                            uploaded_qr_map = {f.name.strip().lower(): f for f in sb_qr_list}
                            first_row = df.iloc[0]

                            company_val = str(first_row['Company Name'])
                            product_val = str(first_row['Product Descriptor'])
                            standard_val = str(first_row['Standard Code'])
                            client_id_val = str(first_row['Client Identifier']).strip()
                            mark_type_val = str(first_row['Mark type']).strip().lower()

                            expected_bulk_filename = f"{client_id_val}-qr-code.png".lower()
                            matched_logo_f = logo_cache.get(mark_type_val)

                            if expected_bulk_filename not in uploaded_qr_map:
                                st.error(f"❌ Asset Mismatch: Repository is missing target row file entry: **{expected_bulk_filename}**")
                            elif not matched_logo_f:
                                st.error(f"❌ Asset Mismatch: Repository is missing target logo schematic file entry: **{mark_type_val.upper()} LOGO.png**")
                            else:
                                try:
                                    qr_img = Image.open(uploaded_qr_map[expected_bulk_filename])
                                    logo_img = Image.open(matched_logo_f)

                                    bulk_preview_render = render_compliance_label(
                                        qr_img, logo_img, company_val, product_val, standard_val, client_id_val, 
                                        ui_width, ui_height, ui_font_sz
                                    )

                                    st.markdown("---")
                                    st.subheader("🔍 Automated Batch First-Row Validation Canvas")
                                    st.image(bulk_preview_render, caption=f"Live Structural Schema Layout Trace for {client_id_val}", use_container_width=True)
                                    st.success("Verification metrics successfully trace inside the container frame layout boundaries.")
                                except Exception as err:
                                    st.error(f"Bulk row diagnostics rendering encountered an exception: {err}")

                    if execute_bulk:
                        if sb_logo_list and sb_qr_list:
                            uploaded_qr_map = {f.name.strip().lower(): f for f in sb_qr_list}
                            zip_buffer = io.BytesIO()
                            compliance_failures = 0
                            skipped_identifiers = []

                            bulk_esm_added = 0
                            bulk_eff_added = 0
                            bulk_other_added = 0

                            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                                progress_bar = st.progress(0)

                                for idx, row in df.iterrows():
                                    company_val = str(row['Company Name'])
                                    product_val = str(row['Product Descriptor'])
                                    standard_val = str(row['Standard Code'])
                                    client_id_val = str(row['Client Identifier']).strip()
                                    mark_type_val = str(row['Mark type']).strip().lower()

                                    expected_bulk_filename = f"{client_id_val}-qr-code.png".lower()
                                    matched_logo_f = logo_cache.get(mark_type_val)

                                    if expected_bulk_filename not in uploaded_qr_map or not matched_logo_f:
                                        compliance_failures += 1
                                        skipped_identifiers.append(f"{client_id_val}")
                                        continue

                                    qr_file_handle = uploaded_qr_map[expected_bulk_filename]
                                    qr = Image.open(qr_file_handle)
                                    logo = Image.open(matched_logo_f)

                                    single_img = render_compliance_label(qr, logo, company_val, product_val, standard_val, client_id_val, ui_width, ui_height, ui_font_sz)

                                    img_buf = io.BytesIO()
                                    single_img.save(img_buf, format="PNG")

                                    safe_client_id = re.sub(r'[^\w\-_\. ]', '_', client_id_val)
                                    zip_file.writestr(f"DSM_Label_{safe_client_id}.png", img_buf.getvalue())

                                    if mark_type_val == "esm":
                                        bulk_esm_added += 1
                                    elif mark_type_val == "eff":
                                        bulk_eff_added += 1
                                    else:
                                        bulk_other_added += 1

                                    progress_bar.progress((idx + 1) / len(df))

                            if compliance_failures == len(df):
                                st.error(f"❌ Generation Terminated: Zero files matched matching configuration names.")
                            else:
                                st.session_state.stats_total_esm += bulk_esm_added
                                st.session_state.stats_total_eff += bulk_eff_added
                                st.session_state.stats_total_other += bulk_other_added

                                st.success(f"Successfully processed {len(df) - compliance_failures} labels.")

                                # CRITICAL FIX: Seek to beginning before reading zip buffer
                                zip_buffer.seek(0)
                                st.download_button(label="Download Archive (ZIP)", data=zip_buffer.getvalue(), file_name="Bulk_Labels.zip", mime="application/zip", key="bulk_zip_download_button", use_container_width=True)
                        else:
                            st.warning("Please upload institutional logos and selection QR configurations in the left sidebar workspace repository.")
            except Exception as e:
                st.error(f"Bulk engine failure: {e}")

# =========================================================================
# TAB 3: 🛡️ ADMIN IDENTITY CONTROL PANEL (REPLACEMENT BLOCK)
# =========================================================================
if IS_ADMIN:
    with tabs_objects[2]:
        st.subheader("System Identity Access Directories")
        st.caption("Manage registrations and grant specific security clearance profiles to ecosystem users.")

        # --- PASSWORD VISIBILITY TOGGLE ---
        if "admin_view_passwords" not in st.session_state:
            st.session_state.admin_view_passwords = False

        st.session_state.admin_view_passwords = st.toggle(
            "Authorize Raw Password Visibility", 
            value=st.session_state.admin_view_passwords,
            help="Enable this to view raw user credentials for administrative audit purposes."
        )

        adm_col1, adm_col2 = st.columns([1, 2])

        with adm_col1:
            st.markdown("**Directly Authorize / Adjust User**")
            new_email = st.text_input("Account Email Address", key="adm_new_email_field").strip().lower()
            new_name = st.text_input("Account Employee Full Name", key="adm_new_name_field").strip()
            new_password = st.text_input("Assign Access Password", type="password", key="adm_new_password_field").strip()
            new_role = st.selectbox("Assigned Clearance Profile", ["Admin", "User", "Guest"], key="adm_new_role_field")

            if st.button("Update Clearance Matrix", type="primary", use_container_width=True):
                if not new_email or not new_name or not new_password:
                    st.error("❌ Registration Blocked: Email, Name, and Password entries are required fields.")
                else:
                    live_reg = load_global_registry()
                    live_reg[new_email] = {
                        "role": new_role, 
                        "name": new_name,
                        "password": new_password,
                        "verified": True
                    }
                    save_global_registry(live_reg)
                    st.success(f"Clearance matrix structuralized for: {new_email}")
                    st.rerun()

        with adm_col2:
            st.markdown("**Active Authorized System Users Registry**")
            live_reg = load_global_registry()
            reg_records = []
            for email, data in live_reg.items():
                # Logic to determine password display based on toggle state
                pwd_display = data.get("password") if st.session_state.admin_view_passwords else "••••••••"

                reg_records.append({
                    "Email Address": email, 
                    "Assigned Role Profile": data["role"], 
                    "Employee Name": data["name"],
                    "Password": pwd_display if data.get("password") else "NOT SET",
                    "Email Verified Status": "Verified ✅" if data.get("verified") else "Unverified ⏳"
                })

            st.table(pd.DataFrame(reg_records))