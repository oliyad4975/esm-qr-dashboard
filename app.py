import io
import os
import re
import textwrap
import zipfile
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# Import ReportLab Engines for crisp PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# -------------------------------------------------------------------------
# STYLING & VIEWPORT CONFIGURATION (STRICT RED-TO-BLUE TAB ENGINE)
# -------------------------------------------------------------------------
st.set_page_config(
    page_title="Digital Standards Mark (DSM) Unique Client Batch ID Generator",
    page_icon="🇪🇹",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    /* 1. Main Dashboard Background Canvas */
    [data-testid="stAppViewContainer"] {
        background-color: #E0F2FE !important;
    }
    
    /* 2. Strict Red-to-Blue Tab State Transition Engine */
    div[data-testid="stTabBar"] {
        background-color: transparent !important;
        border-bottom: 2px solid #E0F2FE !important;
        padding-bottom: 4px !important;
    }
    
    /* Target all tab buttons globally - INITIAL STATE (INACTIVE CORPORATE RED) */
    div[data-testid="stTabBar"] button,
    div[data-testid="stTabBar"] [data-baseweb="tab"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0.6rem 1.2rem !important;
        margin-right: 0.5rem !important;
        transition: all 0.2s ease-in-out !important;
    }

    /* Force deep child selectors to clear browser cache and template native themes */
    div[data-testid="stTabBar"] button p,
    div[data-testid="stTabBar"] [data-baseweb="tab"] p,
    div[data-testid="stTabBar"] button div,
    div[data-testid="stTabBar"] [data-baseweb="tab"] div {
        color: #DC2626 !important; /* Sharp High-Visibility Corporate Red */
        font-weight: bold !important;
        font-size: 16px !important;
    }
    
    /* Hover state performance adjustment */
    div[data-testid="stTabBar"] button:hover p,
    div[data-testid="stTabBar"] [data-baseweb="tab"]:hover p {
        color: #B91C1C !important;
    }
    
    /* ACTIVE STATE OVERRIDE (WHEN CLICKED -> CORPORATE BLUE) */
    div[data-testid="stTabBar"] button[aria-selected="true"],
    div[data-testid="stTabBar"] [data-baseweb="tab"][aria-selected="true"] {
        background-color: transparent !important;
        border-bottom: 4px solid #0000FF !important; /* Pure corporate blue bottom underline */
    }
    
    div[data-testid="stTabBar"] button[aria-selected="true"] p,
    div[data-testid="stTabBar"] [data-baseweb="tab"][aria-selected="true"] p,
    div[data-testid="stTabBar"] button[aria-selected="true"] div,
    div[data-testid="stTabBar"] [data-baseweb="tab"][aria-selected="true"] div {
        color: #0000FF !important; /* Deep Corporate Blue text presentation */
        font-weight: bold !important;
    }

    /* 3. Shaded Heading Panel (Automated Execution Configuration Room) */
    .shaded-header-panel {
        background-color: #1E40AF !important; 
        color: #FFFFFF !important;            
        font-size: 1.8rem !important;
        font-weight: bold !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 4px !important;
        margin-top: 1.5rem !important;
        margin-bottom: 1.5rem !important;
        display: inline-block !important;      
        box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.15);
    }
    
    /* 4. Styled Header Banner Box Architecture */
    .main-title-container { 
        background-color: #0000FF !important; 
        padding: 1.5rem !important;
        border-radius: 4px !important;
        text-align: center !important;
        margin-bottom: 2rem !important;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    .title-line-primary {
        font-size: 3.2rem !important; 
        color: #FFFFFF !important; 
        font-weight: 700 !important; 
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;
        letter-spacing: 0.05rem !important;
    }
    .title-line-secondary {
        font-size: 2.1rem !important; 
        color: #FFFFFF !important; 
        font-weight: 500 !important; 
        margin: 0.4rem 0 0 0 !important;
        padding: 0 !important;
        letter-spacing: 0.02rem !important;
    }
    
    /* Global Widget Labels Forced to 14px and Bold Font Size */
    [data-testid="stWidgetLabel"] p {
        font-size: 14px !important;
        font-weight: bold !important;
        color: #1F2937 !important;
    }
    
    .sub-title { 
        font-size: 1.1rem !important; 
        color: #1E3A8A !important; 
        font-weight: 500;
        margin-bottom: 2rem; 
        text-align: center; 
    }
    
    .success-panel { border-radius: 8px; padding: 1.5rem; background-color: #F0FDF4; border-left: 6px solid #16A34A; margin-top: 1.5rem; }
    </style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------------
# DUAL-COLUMN GRAPHIC RENDER ENGINE
# -------------------------------------------------------------------------
def render_blueprint_compliance_label(
    qr_raw_img, logo_raw_img, company_txt, product_txt, standard_txt, client_txt, c_width, c_height, base_f_size
):
    """Compiles high-resolution assets into a structured dual-column compliance card."""
    label_canvas = Image.new("RGB", (c_width, c_height), color=(255, 255, 255))
    draw_interface = ImageDraw.Draw(label_canvas)

    qr_target_dim = int(c_height * 0.86)
    logo_target_dim = int(c_height * 0.38)
    
    qr_x_origin = int(c_width * 0.04)
    qr_y_origin = (c_height - qr_target_dim) // 2
    
    right_column_center_x = int(c_width - (c_width - qr_target_dim) / 1.85)
    text_wrap_limit = int(26 * (c_width / 1200))

    try:
        font_header = ImageFont.truetype("arialbd.ttf", base_f_size)
        font_metadata = ImageFont.truetype("arialbd.ttf", int(base_f_size * 0.80))
        font_meta_bold = ImageFont.truetype("arialbd.ttf", int(base_f_size * 0.85))
    except IOError:
        font_header = ImageFont.load_default()
        font_metadata = ImageFont.load_default()
        font_meta_bold = ImageFont.load_default()

    if qr_raw_img:
        qr_clean = qr_raw_img.convert("RGBA").resize((qr_target_dim, qr_target_dim), Image.Resampling.LANCZOS)
        label_canvas.paste(qr_clean, (qr_x_origin, qr_y_origin), qr_clean)

    y_text_cursor = int(c_height * 0.06)
    company_lines = textwrap.wrap(str(company_txt).upper(), width=text_wrap_limit)
    
    for line in company_lines:
        left, top, right, bottom = draw_interface.textbbox((0, 0), line, font=font_header)
        line_w = right - left
        line_h = bottom - top
        draw_interface.text((right_column_center_x - (line_w // 2), y_text_cursor), line, fill=(0, 0, 0), font=font_header)
        y_text_cursor += line_h + int(base_f_size * 0.25)

    if logo_raw_img:
        logo_clean = logo_raw_img.convert("RGBA").resize((logo_target_dim, logo_target_dim), Image.Resampling.LANCZOS)
        logo_y_pos = int(c_height * 0.28)
        logo_x_pos = right_column_center_x - (logo_target_dim // 2)
        label_canvas.paste(logo_clean, (logo_x_pos, logo_y_pos), logo_clean)

    meta_stack_collection = []
    if product_txt and str(product_txt).lower() != 'nan':
        meta_stack_collection.append((str(product_txt).upper(), font_meta_bold))
        
    if standard_txt and str(standard_txt).lower() != 'nan':
        std_val = str(standard_txt).upper()
        display_std = f"STANDARD R/NO: {std_val}" if "STANDARD" not in std_val else std_val
        meta_stack_collection.append((display_std, font_metadata))
        
    if client_txt and str(client_txt).lower() != 'nan':
        client_val = str(client_txt).upper()
        display_client = f"CLIENT CODE: {client_val}" if "CLIENT" not in client_val else client_val
        meta_stack_collection.append((display_client, font_metadata))

    y_text_cursor = int(c_height * 0.72)
    for info_string, font_style in meta_stack_collection:
        if info_string.strip():
            left, top, right, bottom = draw_interface.textbbox((0, 0), info_string, font=font_style)
            item_w = right - left
            item_h = bottom - top
            draw_interface.text((right_column_center_x - (item_w // 2), y_text_cursor), info_string, fill=(0, 0, 0), font=font_style)
            y_text_cursor += item_h + int(base_f_size * 0.25)

    return label_canvas

# -------------------------------------------------------------------------
# ADAPTIVE FUZZY DEEP SEARCH INGESTION SUBROUTINE
# -------------------------------------------------------------------------
def clean_token(val):
    return re.sub(r'[^a-z0-9]', '', str(val).lower().strip())

def parse_and_validate_excel_adaptive(workbook_buffer):
    """Deep scans rows of the uploaded file to locate the correct metadata starting grid."""
    raw_df = pd.read_excel(workbook_buffer, header=None)
    
    target_keywords = {"companyname", "company", "producttype", "product", "clientcode", "standardrno", "qrfilename"}
    header_row_index = 0
    found_valid_header_grid = False

    for idx in range(min(25, len(raw_df))):
        row_tokens = [clean_token(cell) for cell in raw_df.iloc[idx].dropna()]
        matches = [tok for tok in row_tokens if any(key in tok for key in target_keywords)]
        
        if len(matches) >= 2:
            header_row_index = idx
            found_valid_header_grid = True
            break

    if found_valid_header_grid:
        final_df = pd.read_excel(workbook_buffer, skiprows=header_row_index)
    else:
        final_df = pd.read_excel(workbook_buffer)

    final_df.columns = [str(c).strip() for c in final_df.columns]
    norm_mapping = {clean_token(col): col for col in final_df.columns}
    
    def resolve_header_leniently(search_variants, fallback_default):
        for variant in search_variants:
            cleaned_var = clean_token(variant)
            if cleaned_var in norm_mapping:
                return norm_mapping[cleaned_var]
            for native_col in norm_mapping:
                if cleaned_var in native_col or native_col in cleaned_var:
                    return norm_mapping[native_col]
        return fallback_default

    resolved_schema = {
        "company": resolve_header_leniently(["company name", "company_name", "company"], "Company Name"),
        "product": resolve_header_leniently(["product type", "product_type", "product"], "Product Type"),
        "client": resolve_header_leniently(["client code", "client_code", "client"], "Client Code"),
        "standard": resolve_header_leniently(["standard r/n", "standard r/no", "standard_rn", "standard"], "Standard R/No"),
        "qr": resolve_header_leniently(["qr filename", "qr_filename", "qr file"], "QR Filename")
    }

    if resolved_schema["company"] not in final_df.columns or resolved_schema["qr"] not in final_df.columns:
        all_found = ", ".join([f"'{x}'" for x in final_df.columns])
        raise KeyError(
            f"Fuzzy lookup engine failed to locate mandatory columns. "
            f"Detected headers in parsed layer: {all_found}"
        )

    return final_df, resolved_schema

# -------------------------------------------------------------------------
# INTERFACE CONTROL DECK
# -------------------------------------------------------------------------
st.markdown("""
    <div class='main-title-container'>
        <div class='title-line-primary'>Digital Standards Mark (DSM)</div>
        <div class='title-line-secondary'>Unique Client Batch ID Generator</div>
    </div>
""", unsafe_allow_html=True)

st.markdown("<div class='sub-title'>High-Level Official Verification Console & Multi-Field Graphic Assembly Line</div>", unsafe_allow_html=True)

st.sidebar.markdown("### 🎛️ Geometric Canvas Controllers")
ui_width = st.sidebar.slider("Label Output Pixel Width", 800, 2400, 1200, step=100)
ui_height = st.sidebar.slider("Label Output Pixel Height", 500, 1500, 800, step=100)
ui_font_sz = st.sidebar.slider("Base Label Font Size", 16, 60, 36, step=2)

st.sidebar.markdown("---")
ui_disk_path = st.sidebar.text_input("Local Output Directory Target Path", value="output/esm_labels/")

# Shaded Tab Interfaces generated natively via advanced CSS dynamic injector block above
tab_production, tab_sandbox = st.tabs(["🚀 Automated Pipeline Room", "🔍 Live Vector Structural Sandbox"])

# 1. LIVE SANDBOX CALIBRATION TAB
with tab_sandbox:
    st.markdown("<div class='shaded-header-panel'>Isolated Layout Vector Verification</div>", unsafe_allow_html=True)
    box_c1, box_c2 = st.columns(2)
    with box_c1:
        sb_company = st.text_input("Corporate Identifier Line", "EMEBET COMMERCIAL BEE KEEPING PLC")
        sb_product = st.text_input("Product Designation Line", "HONEY")
        sb_standard = st.text_input("Regulatory Protocol Tracking Code", "ES 6843:2026")
        sb_client = st.text_input("Registered Enterprise Entity Reference", "EAS-C-0091")
    with box_c2:
        sb_logo_upload = st.file_uploader("Upload National Certificate Logo Symbol Image", type=["png", "jpg", "jpeg"], key="sb_logo")
        sb_qr_upload = st.file_uploader("Upload Targeted Asset Matrix QR Reference", type=["png", "jpg", "jpeg"], key="sb_qr")

    if st.button("Generate Layout Preview Vector", type="secondary"):
        if sb_logo_upload and sb_qr_upload:
            preview_image_result = render_blueprint_compliance_label(
                Image.open(sb_qr_upload), Image.open(sb_logo_upload),
                sb_company, sb_product, sb_standard, sb_client,
                ui_width, ui_height, ui_font_sz
            )
            st.image(preview_image_result, caption="Calculated Frame Layout Output Matrix Grid", use_container_width=True)
        else:
            st.error("Please provide validation upload images.")

# 2. RUNTIME AUTOMATION PIPELINE ROOM
with tab_production:
    st.markdown("<div class='shaded-header-panel'>Automated Execution Configuration Room</div>", unsafe_allow_html=True)
    
    u_col1, u_col2 = st.columns(2)
    with u_col1:
        input_excel = st.file_uploader("1. Drop Corporate Record Source File Registry (Excel format)", type=["xlsx", "xls"])
    with u_col2:
        input_logo = st.file_uploader("2. Drop Corporate National Mark Vector Asset (ESM LOGO.png)", type=["png", "jpg", "jpeg"])

    input_bulk_qrs = st.file_uploader(
        "3. Drop All Matrix QR Code Images Associated with Workspace Rows",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    if "zip_stream_bytes" not in st.session_state:
        st.session_state.zip_stream_bytes = None
    if "pdf_stream_bytes" not in st.session_state:
        st.session_state.pdf_stream_bytes = None
    if "is_process_clean" not in st.session_state:
        st.session_state.is_process_clean = False
    if "total_compiled" not in st.session_state:
        st.session_state.total_compiled = 0

    if st.button("Execute Complex Batch Production Pipeline", type="primary"):
        if not input_excel or not input_logo or not input_bulk_qrs:
            st.error("Missing critical batch engine dependencies.")
        else:
            try:
                src_dataframe, computed_headers = parse_and_validate_excel_adaptive(input_excel)
                
                hdr_comp = computed_headers["company"]
                hdr_prod = computed_headers["product"]
                hdr_client = computed_headers["client"]
                hdr_std = computed_headers["standard"]
                hdr_qr = computed_headers["qr"]

                scrubbed_dataframe = src_dataframe.dropna(subset=[hdr_comp, hdr_qr]).copy()
                
                if scrubbed_dataframe.empty:
                    st.error("Spreadsheet Ingestion Failed: No usable row records identified.")
                else:
                    os.makedirs(ui_disk_path, exist_ok=True)
                    loaded_logo_obj = Image.open(input_logo)

                    system_qr_ram_cache = {}
                    for file_pointer in input_bulk_qrs:
                        standard_filename_key = str(file_pointer.name).strip().lower()
                        system_qr_ram_cache[standard_filename_key] = file_pointer
                        stripped_variant = re.sub(r'\s*\(\d+\)', '', standard_filename_key)
                        system_qr_ram_cache[stripped_variant] = file_pointer

                    batch_progressbar = st.progress(0)
                    batch_status_card = st.empty()
                    total_work_items = len(scrubbed_dataframe)
                    st.session_state.total_compiled = 0

                    compressed_binary_stream = io.BytesIO()
                    pdf_binary_stream = io.BytesIO()
                    
                    pdf_canvas = canvas.Canvas(pdf_binary_stream, pagesize=letter)
                    page_w, page_h = letter

                    with zipfile.ZipFile(compressed_binary_stream, "w", zipfile.ZIP_DEFLATED) as zip_envelope:
                        for row_idx, row_values in scrubbed_dataframe.iterrows():
                            val_company = str(row_values.get(hdr_comp, "")).strip()
                            val_product = str(row_values.get(hdr_prod, "")).strip()
                            val_client = str(row_values.get(hdr_client, "")).strip()
                            val_standard = str(row_values.get(hdr_std, "")).strip()
                            val_qr_name = str(row_values.get(hdr_qr, "")).strip()

                            if not val_qr_name or val_qr_name.lower() == 'nan' or val_company.lower() == 'nan':
                                continue

                            batch_status_card.markdown(f"⚙️ *Compiling Vector Layout:* **{st.session_state.total_compiled + 1}/{total_work_items}** — `{val_company[:42]}...`")
                            
                            target_lookup_string = val_qr_name.lower().strip()
                            target_lookup_stripped = re.sub(r'\s*\(\d+\)', '', target_lookup_string)

                            matched_asset_pointer = None
                            if target_lookup_string in system_qr_ram_cache:
                                matched_asset_pointer = system_qr_ram_cache[target_lookup_string]
                            elif target_lookup_stripped in system_qr_ram_cache:
                                matched_asset_pointer = system_qr_ram_cache[target_lookup_stripped]
                            elif target_lookup_string + ".png" in system_qr_ram_cache:
                                matched_asset_pointer = system_qr_ram_cache[target_lookup_string + ".png"]
                            elif target_lookup_string + ".jpg" in system_qr_ram_cache:
                                matched_asset_pointer = system_qr_ram_cache[target_lookup_string + ".jpg"]

                            if matched_asset_pointer:
                                loaded_qr_obj = Image.open(matched_asset_pointer)

                                final_compiled_vector = render_blueprint_compliance_label(
                                    loaded_qr_obj, loaded_logo_obj,
                                    val_company, val_product, val_standard, val_client,
                                    ui_width, ui_height, ui_font_sz
                                )

                                sanitized_id = val_client.replace('/', '_').replace('\\', '_') if val_client and val_client.lower() != 'nan' else f"Row_{row_idx}"
                                export_file_name = f"Label_{sanitized_id}.jpg"
                                
                                final_compiled_vector.save(os.path.join(ui_disk_path, export_file_name), "JPEG", quality=95)

                                internal_img_ram_buffer = io.BytesIO()
                                final_compiled_vector.save(internal_img_ram_buffer, format="JPEG", quality=95)
                                zip_envelope.writestr(export_file_name, internal_img_ram_buffer.getvalue())

                                internal_img_ram_buffer.seek(0)
                                pdf_image = Image.open(internal_img_ram_buffer)
                                
                                scale_factor = min((page_w - 54) / pdf_image.width, (page_h - 54) / pdf_image.height)
                                draw_w = pdf_image.width * scale_factor
                                draw_h = pdf_image.height * scale_factor
                                x_offset = (page_w - draw_w) / 2
                                y_offset = (page_h - draw_h) / 2

                                pdf_canvas.drawImage(
                                    internal_img_ram_buffer, 
                                    x_offset, y_offset, 
                                    width=draw_w, height=draw_h
                                )
                                pdf_canvas.showPage()

                                st.session_state.total_compiled += 1

                            batch_progressbar.progress((row_idx + 1) / total_work_items)

                    pdf_canvas.save()
                    batch_status_card.empty()
                    
                    compressed_binary_stream.seek(0)
                    pdf_binary_stream.seek(0)
                    
                    st.session_state.zip_stream_bytes = compressed_binary_stream.getvalue()
                    st.session_state.pdf_stream_bytes = pdf_binary_stream.getvalue()
                    st.session_state.is_process_clean = True

            except Exception as system_pipeline_fault:
                st.error(f"Critical Runtime Exception Error: {str(system_pipeline_fault)}")

    # -------------------------------------------------------------------------
    # DUAL-FORMAT DOWNLOAD CONSOLE DECK
    # -------------------------------------------------------------------------
    if st.session_state.is_process_clean and st.session_state.zip_stream_bytes:
        st.markdown(
            f"""
            <div class='success-panel'>
                <h4 style='color: #15A34A; margin-top: 0;'>✅ Automated Multi-Field Pipeline Generation Complete</h4>
                <p style='color: #1F2937; margin-bottom: 0;'>Processed and compiled <b>{st.session_state.total_compiled}</b> compliance card assets.</p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        dl_col1, dl_col2 = st.columns(2)
        
        with dl_col1:
            st.download_button(
                label="📥 DOWNLOAD ALL LABELS AS COMPRESSED ARCHIVE (ZIP)",
                data=st.session_state.zip_stream_bytes,
                file_name="dsm_batch_labels.zip",
                mime="application/zip",
                use_container_width=True
            )
            
        with dl_col2:
            st.download_button(
                label="📄 DOWNLOAD ALL LABELS AS COMPILED REGISTER (PDF)",
                data=st.session_state.pdf_stream_bytes,
                file_name="dsm_batch_register.pdf",
                mime="application/pdf",
                use_container_width=True
            )