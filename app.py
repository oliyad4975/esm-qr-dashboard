import io
import os
import re
import textwrap
import zipfile
import platform
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# Import ReportLab Engines for crisp PDF generation and in-memory image streaming
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

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

# Define permanent path for the institutional logo asset
PERMANENT_IES_LOGO_PATH = os.path.join("static", "ies_logo.png")

# -------------------------------------------------------------------------
# INITIALIZE GLOBAL IDENTITY MANAGEMENT DATABASE WITH PASSWORDS (RBAC)
# -------------------------------------------------------------------------
if "user_registry" not in st.session_state:
    # Pre-seeded system registry with dedicated credentials for all core accounts
    st.session_state.user_registry = {
        "oliyad4975@yahoo.com": {"role": "Admin", "name": "Oliyad Lencho Desure", "password": "AdminPassword123", "verified": True},
        "operator@ies.gov.et": {"role": "User", "name": "Technical Officer", "password": "OperatorPassword456", "verified": True},
        "guest@ies.gov.et": {"role": "Guest", "name": "Institutional Observer", "password": "GuestPassword789", "verified": True}
    }

if "current_user" not in st.session_state:
    st.session_state.current_user = None

# -------------------------------------------------------------------------
# INTERCEPT URL QUERY PARAMETERS FOR EMAIL VERIFICATION ROUTING
# -------------------------------------------------------------------------
query_params = st.query_params
if "verify_email" in query_params and "token" in query_params:
    target_v_email = urllib.parse.unquote(query_params["verify_email"]).strip().lower()
    provided_token = query_params["token"]
    
    if target_v_email in st.session_state.user_registry:
        expected_token = f"TOKEN_{target_v_email.split('@')[0].upper()}_SECURE"
        if provided_token == expected_token:
            st.session_state.user_registry[target_v_email]["verified"] = True
            st.session_state.current_user = {
                "email": target_v_email,
                "role": st.session_state.user_registry[target_v_email]["role"],
                "name": st.session_state.user_registry[target_v_email]["name"]
            }
            st.query_params.clear()
            st.toast(f"✅ Email verified automatically! Session routing initialized for {st.session_state.current_user['name']}.", icon="🔓")
            st.rerun()
        else:
            st.sidebar.error("❌ Link Routing Error: Security token structural signature is invalid or has expired.")
    else:
        st.sidebar.error("❌ Link Routing Error: User tracking record reference missing inside ecosystem cluster.")

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
    st.markdown("<div style='max-width: 550px; margin: 40px auto; padding: 2rem; border: 1px solid #E0E0E0; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); background-color: white;'>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center; color: #FF0000; margin-top: 0;'>🔒 IES Verifier IAM Gateway</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666666; font-size: 0.9rem;'>Identity Access Management for Certification Schemes & Standard Mark Administration</p>", unsafe_allow_html=True)
    
    auth_tab1, auth_tab2, auth_tab3 = st.tabs(["Existing User Sign-In", "New User Registration", "🔑 Recovery & Password Reset"])
    
    with auth_tab1:
        st.markdown("<br>", unsafe_allow_html=True)
        login_email = st.text_input("Institutional Email Address", key="auth_login_email").strip().lower()
        login_password = st.text_input("Account Password", type="password", key="auth_login_password")
        
        if st.button("Authenticate Secure Session", type="primary", use_container_width=True, key="login_submit_btn"):
            if not login_email or not login_password:
                st.error("❌ Identification Required: Both email address and password must be provided.")
            elif login_email in st.session_state.user_registry:
                user_info = st.session_state.user_registry[login_email]
                if not user_info.get("verified", False):
                    st.error("❌ Access Blocked: This email identity is unverified! Please look up or execute your pending email verification redirect routing link first.")
                elif login_password == user_info["password"]:
                    st.session_state.current_user = {
                        "email": login_email,
                        "role": user_info["role"],
                        "name": user_info["name"]
                    }
                    st.success(f"Session established successfully. Welcome back, {st.session_state.current_user['name']}.")
                    st.rerun()
                else:
                    st.error("❌ Access Denied: Invalid credentials provided. Please verify your password entry.")
            else:
                st.error("❌ Authentication Refused: The provided email is not registered within this ecosystem database.")
                
    with auth_tab2:
        st.markdown("<br>", unsafe_allow_html=True)
        reg_name = st.text_input("Full Name", key="auth_reg_name").strip()
        reg_email = st.text_input("Account Email Address", key="auth_reg_email").strip().lower()
        reg_password = st.text_input("Choose Account Password", type="password", key="auth_reg_password")
        reg_intent = st.selectbox("Requested Institutional Access Level", ["Guest", "Expert/User"], key="auth_reg_intent")
        
        st.caption("ℹ️ Note: Registration requests automatically default to 'Guest' or 'User' privileges pending Admin evaluation.")
        
        if st.button("Submit Registration Profile", type="secondary", use_container_width=True, key="reg_submit_btn"):
            if not reg_name or not reg_email or not reg_password:
                st.error("❌ Incomplete Profile: Name, email credentials, and a secure password must be completed.")
            elif "@" not in reg_email:
                st.error("❌ Syntax Error: Please provide a valid email structure (e.g., identity@domain.com).")
            elif reg_email in st.session_state.user_registry:
                st.warning("⚠️ Record Exists: This email is already present in the user base register. Proceed to Sign-In.")
            else:
                assigned_role = "User" if "Expert/User" in reg_intent else "Guest"
                st.session_state.user_registry[reg_email] = {
                    "role": assigned_role,
                    "name": reg_name,
                    "password": reg_password,
                    "verified": False
                }
                
                token_hash = f"TOKEN_{reg_email.split('@')[0].upper()}_SECURE"
                encoded_email = urllib.parse.quote(reg_email)
                simulated_verification_url = f"http://localhost:8501/?verify_email={encoded_email}&token={token_hash}"
                
                st.markdown("---")
                st.info("✉️ **Ecosystem Verification Pipeline Dispatched!**\n\nSimulating email payload arrival below:")
                st.markdown(
                    f"""
                    <div style="background-color: #F4F6F8; border-left: 4px solid #FF0000; padding: 15px; margin: 10px 0; border-radius: 4px;">
                        <strong style="color: #333;">From:</strong> Identity Access Management System <br>
                        <strong style="color: #333;">To:</strong> {reg_email} <br>
                        <strong style="color: #333;">Subject:</strong> Verify Institutional Access Account <br><br>
                        Hello {reg_name},<br>
                        Please confirm your identity registration parameters to activate standard system schema clearances.<br><br>
                        <a href="{simulated_verification_url}" target="_self" style="background-color: #FF0000; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block; margin-top: 5px;">Verify Email & Launch Dashboard</a>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
    with auth_tab3:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("🥇 **Self-Service Out-of-Session Recovery**")
        recovery_email = st.text_input("Enter Registered Account Email Address", key="auth_recovery_email").strip().lower()
        new_recovery_pwd = st.text_input("Provide New Target Password String", type="password", key="auth_recovery_new_pwd")
        
        if st.button("Authorize Structural Password Rewrite", type="secondary", use_container_width=True):
            if not recovery_email or not new_recovery_pwd:
                st.error("❌ Profile Alteration Refused: Complete all input forms to establish modifications.")
            elif recovery_email in st.session_state.user_registry:
                st.session_state.user_registry[recovery_email]["password"] = new_recovery_pwd
                st.success("🎉 Passphrase altered successfully within authorization registries! Switch back to 'Existing User Sign-In' to verify session connection access rules.")
            else:
                st.error("❌ Identity Match Failure: Target entry context does not exist.")
                
    st.markdown("</div>", unsafe_allow_html=True)

# Halt execution downstream if authorization tracking context does not exist
if st.session_state.current_user is None:
    render_auth_gateway()
    st.stop()

USER_ROLE = st.session_state.current_user["role"]
IS_ADMIN = (USER_ROLE == "Admin")
IS_USER = (USER_ROLE == "User")
IS_GUEST = (USER_ROLE == "Guest")

# -------------------------------------------------------------------------
# BALANCED SYMMETRIC ENGINE (BERNARD MT CONDENSED - REGULAR WEIGHT)
# -------------------------------------------------------------------------
def render_compliance_label(qr_img, logo_img, company, product, standard, client_id, width, height, font_sz):
    canvas_w = 800
    canvas_h = 450
    img = Image.new("RGB", (canvas_w, canvas_h), color="white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([15, 15, canvas_w - 15, canvas_h - 15], outline="black", width=5)
    
    font_name = "BERNHC.TTF"
    system_font_paths = [
        font_name,
        os.path.join("C:\\", "Windows", "Fonts", font_name),
        os.path.join("C:\\", "Windows", "Fonts", "Bernard MT Condensed.ttf"),
        os.path.join("/Library/Fonts", font_name),
        os.path.join("~/.fonts", font_name)
    ]
    font_loaded = None
    target_size = int(font_sz) if font_sz else 26
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

    qr_box_size = 360
    qr_top_y = (canvas_h - qr_box_size) // 2
    if qr_img:
        qr_resized = qr_img.resize((qr_box_size, qr_box_size), Image.Resampling.LANCZOS)
        img.paste(qr_resized, (35, qr_top_y))
        
    right_center_x = 582  
    display_company = str(company if company else "REGISTERED CLIENT PLC")
    draw.text((right_center_x, 70), display_company, fill="black", anchor="mm", font=font_loaded, stroke_width=0)
    
    logo_size = 180
    if logo_img:
        logo_resized = logo_img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        if logo_resized.mode in ('RGBA', 'LA') or (logo_resized.mode == 'P' and 'transparency' in logo_resized.info):
            logo_rgba = logo_resized.convert("RGBA")
            background = Image.new("RGBA", logo_rgba.size, (255, 255, 255, 255))
            logo_final = Image.alpha_composite(background, logo_rgba).convert("RGB")
        else:
            logo_final = logo_resized.convert("RGB")
        img.paste(logo_final, (right_center_x - (logo_size // 2), 105))
        
    display_product = str(product if product else "PRODUCT SPECIFICATION DETAIL")
    display_standard = str(standard if standard else "CES / ISO STANDARD")
    display_batch = str(client_id if client_id else "BATCH IDENTIFIER REFERENCE")
    
    draw.text((right_center_x, 325), display_product, fill="black", anchor="mm", font=font_loaded, stroke_width=0)
    draw.text((right_center_x, 353), display_standard, fill="black", anchor="mm", font=font_loaded, stroke_width=0)
    draw.text((right_center_x, 381), display_batch, fill="black", anchor="mm", font=font_loaded, stroke_width=0)
    return img

# -------------------------------------------------------------------------
# INITIAL THEME CONTROL STATES (PRE-RENDER PROFILES)
# -------------------------------------------------------------------------
text_header_color = "#FF0000"
ui_bg_color = "#FFFFFF"
ui_sidebar_bg_color = "#F0F2F6"

chosen_theme = st.session_state.get("top_right_layout_theme", "Default Layout")

# -------------------------------------------------------------------------
# USER INTERFACE SIDEBAR CONTROL PANEL (ASSETS ONLY)
# -------------------------------------------------------------------------
if os.path.exists(PERMANENT_IES_LOGO_PATH):
    try:
        ies_fixed_logo = Image.open(PERMANENT_IES_LOGO_PATH)
        st.sidebar.image(ies_fixed_logo, use_container_width=True)
    except Exception:
        pass

# Restrict custom color configuration menus uniquely to Admin profiles
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
# CENTRAL WORKSPACE ENVIRONMENT & CONSOLIDATED PROFILE DROPDOWN (CLEAN TEXT MAPPING)
# -------------------------------------------------------------------------
hdr_col1, hdr_col2 = st.columns([3.6, 1.4])

with hdr_col1:
    st.markdown(f'<h1 style="color:{text_header_color}; font-size:1.9rem; margin-bottom:0px; margin-top:0px; padding-top:0px; line-height: 1.2;">ETHIOPIAN STANDARD MARK UNIQUE CLIENT ID GENERATOR</h1>', unsafe_allow_html=True)

with hdr_col2:
    # Normalized drop-down label layer displaying pure context information without "v" string characters
    with st.popover(f"👤 {USER_ROLE}", use_container_width=True):
        st.markdown(
            f"""
            <div style='padding: 2px 4px; margin-bottom: 8px; border-bottom: 1px solid #EEEEEE;'>
                <p style='margin:0; font-size:0.8rem; color:#666666;'>Authenticated Active Session:</p>
                <code style='color:#28A745; font-size:0.85rem;'>{st.session_state.current_user['email']}</code>
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        # Action Item 1: Terminate Session (Logout)
        if st.button("🚪 Logout", type="secondary", key="logout_execution_handler", use_container_width=True):
            st.session_state.current_user = None
            st.rerun()
            
        st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
        
        # Action Item 2: Reset Password Interface inside Dropdown Stack
        st.markdown("<p style='font-size:0.85rem; font-weight:bold; margin:4px 0;'>🔄 Reset password parameters:</p>", unsafe_allow_html=True)
        old_sidebar_pwd = st.text_input("Current Password", type="password", key="hdr_old_pwd_field")
        new_sidebar_pwd = st.text_input("New Password", type="password", key="hdr_new_pwd_field")
        
        if st.button("Commit Reset", use_container_width=True, key="hdr_pwd_commit_action_btn"):
            current_active_email = st.session_state.current_user["email"]
            real_registered_pwd = st.session_state.user_registry[current_active_email]["password"]
            
            if not old_sidebar_pwd or not new_sidebar_pwd:
                st.error("Input parameters missing.")
            elif old_sidebar_pwd != real_registered_pwd:
                st.error("Verification Failure: Current mismatch.")
            else:
                st.session_state.user_registry[current_active_email]["password"] = new_sidebar_pwd
                st.success("Credentials updated successfully.")
                
        # Layout Profile Theme Configuration (Internal Context Layer)
        if not IS_GUEST and IS_ADMIN:
            st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
            theme_mode = st.selectbox(
                "Workspace Base Viewport Layout", 
                ["Default Layout", "Custom Color Palette Mode"], 
                key="top_right_layout_theme"
            )
            if theme_mode != chosen_theme:
                st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# Determine active pipeline architecture layout views or separate dedicated user tabs
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
    st.subheader("Certificate Metadata Form Structure")
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
                                
                            st.success("Symmetric margins balanced perfectly across border frames.")
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
                    
                    if sb_logo_list and sb_qr_list:
                        uploaded_qr_map = {f.name.strip().lower(): f for f in sb_qr_list}
                        
                        if st.button("Execute Bulk Label Generation", type="primary", key="bulk_execute_generation_btn"):
                            zip_buffer = io.BytesIO()
                            compliance_failures = 0
                            skipped_identifiers = []
                            
                            bulk_esm_added = 0
                            bulk_eff_added = 0
                            bulk_other_added = 0
                            
                            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
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
                                st.error(f"❌ Generation Terminated: Zero files matched.")
                            else:
                                st.session_state.stats_total_esm += bulk_esm_added
                                st.session_state.stats_total_eff += bulk_eff_added
                                st.session_state.stats_total_other += bulk_other_added
                                
                                st.success(f"Successfully processed {len(df) - compliance_failures} labels.")
                                st.download_button(label="Download Archive (ZIP)", data=zip_buffer.getvalue(), file_name="Bulk_Labels.zip", mime="application/zip", key="bulk_zip_download_button", use_container_width=True)
                                st.rerun()
            except Exception as e:
                st.error(f"Bulk engine failure: {e}")

# =========================================================================
# TAB 3: 🛡️ ADMIN IDENTITY CONTROL PANEL (EXCLUSIVE VIEWPORT)
# =========================================================================
if IS_ADMIN:
    with tabs_objects[2]:
        st.subheader("System Identity Access Directories")
        st.caption("Manage registrations and grant specific security clearance profiles to ecosystem users.")
        
        adm_col1, adm_col2 = st.columns([1, 2])
        
        with adm_col1:
            st.markdown("**Directly Authorize / Adjust User**")
            new_email = st.text_input("Account Email Address", key="adm_new_email_field").strip().lower()
            new_name = st.text_input("Account Employee Full Name", key="adm_new_name_field").strip()
            new_password = st.text_input("Assign Access Password", type="password", key="adm_new_password_field")
            new_role = st.selectbox("Assigned Clearance Profile", ["Admin", "User", "Guest"], key="adm_new_role_field")
            
            if st.button("Update Clearance Matrix", type="primary", use_container_width=True):
                if not new_email or not new_name or not new_password:
                    st.error("❌ Registration Blocked: Email, Name, and Password entries are required fields.")
                elif "@" not in new_email:
                    st.error("❌ Registration Blocked: Input must conform to standard email formatting syntax.")
                else:
                    st.session_state.user_registry[new_email] = {
                        "role": new_role, 
                        "name": new_name,
                        "password": new_password,
                        "verified": True
                    }
                    st.success(f"Clearance matrix structuralized successfully for account: {new_email}")
                    st.rerun()
                    
        with adm_col2:
            st.markdown("**Active Authorized System Users Registry**")
            reg_records = []
            for email, data in st.session_state.user_registry.items():
                reg_records.append({
                    "Email Address": email, 
                    "Assigned Role Profile": data["role"], 
                    "Employee Name": data["name"],
                    "Password String (Masked)": "••••••••" if data.get("password") else "NOT SET",
                    "Email Verified Status": "Verified ✅" if data.get("verified") else "Unverified ⏳"
                })
            
            st.table(pd.DataFrame(reg_records))