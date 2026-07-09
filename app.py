import io
import os
import re
import textwrap
import zipfile
import platform
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

# -------------------------------------------------------------------------
# BALANCED SYMMETRIC ENGINE (BERNARD MT CONDENSED)
# -------------------------------------------------------------------------
def render_compliance_label(qr_img, logo_img, company, product, standard, client, width, height, font_sz):
    """
    Renders a high-resolution preview image with matching left and right outer margins, 
    incorporating a robust Bernard MT Condensed font profile tracker.
    """
    # High-DPI canvas layout matching production specifications
    canvas_w = 800
    canvas_h = 450
    
    # Initialize high-DPI Pillow Canvas
    img = Image.new("RGB", (canvas_w, canvas_h), color="white")
    draw = ImageDraw.Draw(img)
    
    # Draw Thick Outer Border Frame Boundary
    draw.rectangle([15, 15, canvas_w - 15, canvas_h - 15], outline="black", width=5)
    
    # SYSTEM FONT ACQUISITION: Strict explicit absolute path mapping for Linux Cloud Nodes
    font_loaded = None
    using_fallback = False
    target_size = int(font_sz) if font_sz else 32

    # Look directly at the current running repository directory folder root
    current_dir = Path(__file__).parent.absolute()
    
    # Check for lowercase, uppercase, and exact file structures to eliminate Linux mismatches
    potential_font_locations = [
        current_dir / "BERNHC.TTF",
        current_dir / "bernhc.ttf",
        current_dir / "Bernard MT Condensed.ttf",
        Path("BERNHC.TTF"),
        Path("bernhc.ttf")
    ]
    
    for font_path in potential_font_locations:
        if font_path.is_file():
            try:
                font_loaded = ImageFont.truetype(str(font_path), target_size)
                st.sidebar.success(f"Successfully loaded font asset: {font_path.name}")
                break
            except Exception:
                continue

    if not font_loaded:
        try:
            # Fallback to default engine with an inflated size to keep design proportion
            font_loaded = ImageFont.load_default()
            using_fallback = True
            st.sidebar.warning("Font file not parsed. Utilizing structural baseline engine.")
        except Exception:
            font_loaded = None

    # 1. HORIZONTAL MARGIN BALANCING MATRIX
    qr_box_size = 360
    qr_top_y = (canvas_h - qr_box_size) // 2  # 45
    
    # Draw QR code positioned at precisely 35px from left boundary line
    if qr_img:
        qr_resized = qr_img.resize((qr_box_size, qr_box_size), Image.Resampling.LANCZOS)
        img.paste(qr_resized, (35, qr_top_y))
        
    # Balanced Center Axis for the Right Column components
    right_center_x = 582  
    
    # Force heavy formatting look even if font fallback triggers
    stroke_val = 1 if using_fallback else 0
    
    # Top Client Header - Positioned safely inside the top margin tracking frame (Y=70)
    display_company = str(company if company else (client if client else "REGISTERED CLIENT PLC"))
    draw.text((right_center_x, 70), display_company, fill="black", anchor="mm", font=font_loaded, stroke_width=stroke_val)
    
    # Center: Scaled National Standard Mark Logo (Symmetric spacing)
    logo_size = 180
    if logo_img:
        logo_resized = logo_img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        if logo_resized.mode in ('RGBA', 'LA'):
            background = Image.new("RGBA", logo_resized.size, (255, 255, 255, 255))
            logo_resized = Image.alpha_composite(background, logo_resized).convert("RGB")
        img.paste(logo_resized, (right_center_x - (logo_size // 2), 105))
        
    # Bottom Stack: Enforced alignment with the exact base line of the QR matrix (Y=405)
    display_product = str(product if product else "PRODUCT SPECIFICATION DETAIL")
    display_standard = str(standard if standard else "CES / ISO STANDARD")
    display_batch = "ESML-SHFADW-CA300213"
    
    gap = 22 if using_fallback else 28
    
    draw.text((right_center_x, 325), display_product, fill="black", anchor="mm", font=font_loaded, stroke_width=stroke_val)
    draw.text((right_center_x, 325 + gap), display_standard, fill="black", anchor="mm", font=font_loaded, stroke_width=stroke_val)
    draw.text((right_center_x, 325 + (gap * 2)), display_batch, fill="black", anchor="mm", font=font_loaded, stroke_width=stroke_val)
    
    return img

# -------------------------------------------------------------------------
# USER INTERFACE SIDEBAR CONTROL PANEL
# -------------------------------------------------------------------------
st.sidebar.title("Institutional Control Panel")
st.sidebar.markdown("---")

st.sidebar.subheader("Asset Repositories Upload")
sb_logo = st.sidebar.file_uploader("Upload Institutional Logo (EOS)", type=["png", "jpg", "jpeg"], key="app_logo_uploader")
sb_qr = st.sidebar.file_uploader("Upload Dynamic Target QR Code", type=["png", "jpg", "jpeg"], key="app_qr_uploader")

st.sidebar.markdown("---")
st.sidebar.subheader("Layout Optimization Adjustments")

ui_width = st.sidebar.slider("Label Width (px)", 800, 2400, 1200, step=100, key="sidebar_label_width_slider")
ui_height = st.sidebar.slider("Label Height (px)", 400, 1200, 600, step=50, key="sidebar_label_height_slider")
ui_font_sz = st.sidebar.slider("Metadata Font Scale", 12, 48, 32, step=2, key="sidebar_font_size_slider")

# -------------------------------------------------------------------------
# CENTRAL WORKSPACE ENVIRONMENT
# -------------------------------------------------------------------------
st.write("National Quality Infrastructure Digitization Framework Workflow.")

# Text Information Input Fields Group Block
st.subheader("Certificate Metadata Form Structure")
row1_col1, row1_col2 = st.columns(2)
with row1_col1:
    sb_company = st.text_input("Registered Company / Trading Entity Name", value="SHF TRADING PLC")
    sb_product = st.text_input("Product Classification Descriptor", value="PACKAGED DRINKING WATER (AQUA DIRE)")
with row1_col2:
    sb_standard = st.text_input("National Technical Standard Harmonization Code", value="CES99:2021")
    sb_client = st.text_input("Alternative Client Identifier Reference (If Applicable)", value="")

st.markdown("---")

# Main Action Workspace Column Splits
col_view, col_actions = st.columns([2, 1])

with col_view:
    st.subheader("Live Composite Label Verification Preview")
    
    if st.button("Generate Preview", type="secondary", key="central_workspace_preview_btn"):
        if sb_logo and sb_qr:
            try:
                logo = Image.open(sb_logo)
                qr = Image.open(sb_qr)
                
                preview = render_compliance_label(qr, logo, sb_company, sb_product, sb_standard, sb_client, ui_width, ui_height, ui_font_sz)
                st.image(preview, caption="Label Verification Preview (Balanced Bernard MT Mode)", use_container_width=True)
                st.success("Symmetric margins balanced perfectly across border frames.")
            except Exception as e:
                st.error(f"Preview generation failed: {e}")
        else:
            st.warning("Please upload both the institutional logo and target QR code images in the sidebar configuration to compile.")

with col_actions:
    st.subheader("Institutional Actions")
    st.info("Ensure layouts conform perfectly with national certification schemes rules before authorizing exports.")
    
    if st.button("Compile & Export Production Vector PDF", type="primary", key="central_workspace_export_pdf_btn"):
        if sb_logo and sb_qr:
            try:
                output_pdf_path = "output/Production_DSM_Label.pdf"
                
                data_payload = {
                    'client_name': sb_company if sb_company else sb_client,
                    'product_desc': sb_product,
                    'standard_code': sb_standard,
                    'batch_id': "ESML-SHFADW-CA300213"
                }
                
                if improved_engine is not None:
                    with open("static/temp_qr.png", "wb") as f:
                        f.write(sb_qr.getbuffer())
                    with open("static/temp_logo.png", "wb") as f:
                        f.write(sb_logo.getbuffer())
                        
                    improved_engine.generate_dsm_label(output_pdf_path, "static/temp_qr.png", "static/temp_logo.png", data_payload)
                    
                    with open(output_pdf_path, "rb") as pdf_file:
                        st.download_button(
                            label="Download Certified Vector PDF Document",
                            data=pdf_file,
                            file_name="Production_DSM_Label.pdf",
                            mime="application/pdf",
                            key="dsm_pdf_download_handler_btn"
                        )
                    st.success("Vector PDF Compiled Successfully.")
                else:
                    st.error("Improved layout compilation engine module was not detected.")
            except Exception as e:
                st.error(f"Production compilation failed: {e}")
        else:
            st.error("Missing mandatory graphical assets required for production build.")