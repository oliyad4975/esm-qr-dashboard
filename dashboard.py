import io
import os
import re
import textwrap
import zipfile
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# -------------------------------------------------------------------------
# STYLING & VIEWPORT CONFIGURATION
# -------------------------------------------------------------------------
st.set_page_config(
    page_title="National Standards Mark Batch Production Engine",
    page_icon="🇪🇹",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .reportview-container { background: #0F172A; }
    .main-title { font-size: 2.6rem !important; color: #1E40AF; font-weight: 800; letter-spacing: -0.05rem; }
    .sub-title { font-size: 1.1rem !important; color: #4B5563; margin-bottom: 2rem; }
    .success-panel { border-radius: 8px; padding: 1.5rem; background-color: #F0FDF4; border-left: 6px solid #16A34A; margin-top: 1.5rem; }
    </style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------------
# DUAL-COLUMN GRAPHIC RENDER ENGINE (PIC 1 ARCHITECTURE)
# -------------------------------------------------------------------------
def render_blueprint_compliance_label(
    qr_raw_img, logo_raw_img, company_txt, product_txt, standard_txt, client_txt, c_width, c_height, base_f_size
):
    """Compiles high-resolution assets into a structured dual-column compliance card

    following the structural blueprint matrix (Left: QR | Right: Info Stack).
    """
    # 1. Initialize crisp master white canvas surface
    label_canvas = Image.new("RGB", (c_width, c_height), color=(255, 255, 255))
    draw_interface = ImageDraw.Draw(label_canvas)

    # 2. Establish proportional boundaries based on layout constraints
    qr_target_dim = int(c_height * 0.86)
    logo_target_dim = int(c_height * 0.38)
    
    # Calculate exact horizontal and vertical alignment centers
    qr_x_origin = int(c_width * 0.04)
    qr_y_origin = (c_height - qr_target_dim) // 2
    
    # Establish central horizontal dividing axis for the right data block
    right_column_center_x = int(c_width - (c_width - qr_target_dim) / 1.85)
    text_wrap_limit = int(26 * (c_width / 1200))

    # 3. Load scalable typography matrices (with fallback tracking safety)
    try:
        font_header = ImageFont.truetype("arialbd.ttf", base_f_size)
        font_metadata = ImageFont.truetype("arialbd.ttf", int(base_f_size * 0.80))
        font_meta_bold = ImageFont.truetype("arialbd.ttf", int(base_f_size * 0.85))
    except IOError:
        font_header = ImageFont.load_default()
        font_metadata = ImageFont.load_default()
        font_meta_bold = ImageFont.load_default()

    # 4. Render Left Side Element: High-Density QR Code
    if qr_raw_img:
        qr_clean = qr_raw_img.convert("RGBA").resize((qr_target_dim, qr_target_dim), Image.Resampling.LANCZOS)
        label_canvas.paste(qr_clean, (qr_x_origin, qr_y_origin), qr_clean)

    # 5. Render Upper Right Deck: Company Name Header Text Block
    y_text_cursor = int(c_height * 0.06)
    company_lines = textwrap.wrap(str(company_txt).upper(), width=text_wrap_limit)
    
    for line in company_lines:
        left, top, right, bottom = draw_interface.textbbox((0, 0), line, font=font_header)
        line_w = right - left
        line_h = bottom - top
        draw_interface.text((right_column_center_x - (line_w // 2), y_text_cursor), line, fill=(0, 0, 0), font=font_header)
        y_text_cursor += line_h + int(base_f_size * 0.25)

    # 6. Render Middle Right Space: ESM National Standards Mark Logo Emblem
    if logo_raw_img:
        logo_clean = logo_raw_img.convert("RGBA").resize((logo_target_dim, logo_target_dim), Image.Resampling.LANCZOS)
        logo_y_pos = int(c_height * 0.28)
        logo_x_pos = right_column_center_x - (logo_target_dim // 2)
        label_canvas.paste(logo_clean, (logo_x_pos, logo_y_pos), logo_clean)

    # 7. Render Lower Right Base: Metadata Stack Execution Area
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
# FLEXIBLE MATRIX KEY ALIGNMENT ENGINE
# -------------------------------------------------------------------------
def clean_string_token(input_string):
    return re.sub(r'[^a-z0-9]', '', str(input_string).lower().strip())

def parse_and_validate_excel(workbook_buffer):
    """Loads dataframe worksheets and normalizes heterogeneous data keys safely."""
    parsed_df = pd.read_excel(workbook_buffer)
    parsed_df.columns = [str(c).strip() for c in parsed_df.columns]
    
    normalized_mapping = {clean_string_token(col): col for col in parsed_df.columns}
    
    def fetch_true_column_header(alternatives, semantic_label):
        for candidate in alternatives:
            cleaned_candidate = clean_string_token(candidate)
            if cleaned_candidate in normalized_mapping:
                return normalized_mapping[cleaned_candidate]
            for core_key in normalized_mapping:
                if cleaned_candidate in core_key or core_key in cleaned_candidate:
                    return normalized_mapping[core_key]
        all_found = ", ".join([f"'{x}'" for x in parsed_df.columns])
        raise KeyError(f"Required structural descriptor matching reference '{semantic_label}' was not found. Detected headers: {all_found}")

    resolved_schema = {
        "company": fetch_true_column_header(["company name", "company_name", "company", "enterprise"], "Company Name"),
        "product": fetch_true_column_header(["product type", "product_type", "product", "type"], "Product Type"),
        "client": fetch_true_column_header(["client code", "client_code", "client"], "Client Code"),
        "standard": fetch_true_column_header(["standard r/n", "standard r/no", "standard_rn", "standard"], "Standard R/N"),
        "qr": fetch_true_column_header(["qr filename", "qr_filename", "qr file"], "QR Filename")
    }
    return parsed_df, resolved_schema

# -------------------------------------------------------------------------
# INTERFACE CONTROL DECK
# -------------------------------------------------------------------------
st.markdown("<div class='main-title'>National Standards Mark (ESM) Batch Engine</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>High-Level Official Verification Console & Multi-Field Graphic Assembly Line</div>", unsafe_allow_html=True)

# Layout modification dashboard controllers
st.sidebar.markdown("### 🎛️ Geometric Canvas Controllers")
ui_width = st.sidebar.slider("Label Output Pixel Width", 800, 2400, 1200, step=100)
ui_height = st.sidebar.slider("Label Output Pixel Height", 500, 1500, 800, step=100)
ui_font_sz = st.sidebar.slider("Base Label Font Size", 16, 60, 36, step=2)

st.sidebar.markdown("---")
ui_disk_path = st.sidebar.text_input("Local Environment Output Directory Target Path", value="output/esm_labels/")

tab_production, tab_sandbox = st.tabs(["🚀 Automated Pipeline Room", "🔍 Live Vector Structural Sandbox"])

# 1. LIVE SANDBOX CALIBRATION TAB
with tab_sandbox:
    st.subheader("Isolated Layout Vector Verification")
    st.markdown("Use this panel to calibrate rendering parameters before triggering large file batches.")
    
    box_c1, box_c2 = st.columns(2)
    with box_c1:
        sb_company = st.text_input("Corporate Identifier Line", "EMEBET COMMERCIAL BEE KEEPING FOR ENVIRONMENT PLC")
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
            
            isolated_buffer = io.BytesIO()
            preview_image_result.save(isolated_buffer, format="JPEG", quality=95)
            st.download_button("📥 Export This Isolated Sample Label", data=isolated_buffer.getvalue(), file_name="esm_individual_sample.jpg", mime="image/jpeg")
        else:
            st.error("Please ensure you upload both a valid QR matrix sample and the corporate logo asset to run a visual test.")

# 2. RUNTIME AUTOMATION PIPELINE ROOM
with tab_production:
    st.subheader("Automated Execution Configuration Room")
    
    u_col1, u_col2 = st.columns(2)
    with u_col1:
        input_excel = st.file_uploader("1. Drop Corporate Record Source File Registry (Excel format)", type=["xlsx", "xls"])
    with u_col2:
        input_logo = st.file_uploader("2. Drop Corporate National Mark Vector Asset (ESM LOGO.png)", type=["png", "jpg", "jpeg"])

    input_bulk_qrs = st.file_uploader(
        "3. Drop All Matrix QR Code Images Associated with Workspace Rows (Multi-Selection File Dropzone)",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    # Session persistence setup
    if "zip_stream_bytes" not in st.session_state:
        st.session_state.zip_stream_bytes = None
    if "is_process_clean" not in st.session_state:
        st.session_state.is_process_clean = False
    if "total_compiled" not in st.session_state:
        st.session_state.total_compiled = 0

    if st.button("Execute Complex Batch Production Pipeline", type="primary"):
        if not input_excel or not input_logo or not input_bulk_qrs:
            st.error("Missing critical batch engine dependencies. Check file registry assets, reference symbols, or target matrix directories.")
        else:
            try:
                # Parse data registry worksheet sheets safely
                src_dataframe, computed_headers = parse_and_validate_excel(input_excel)
                
                # Deconstruct column tracking indexes
                hdr_comp = computed_headers["company"]
                hdr_prod = computed_headers["product"]
                hdr_client = computed_headers["client"]
                hdr_std = computed_headers["standard"]
                hdr_qr = computed_headers["qr"]

                # Prune incomplete rows safely
                scrubbed_dataframe = src_dataframe.dropna(subset=[hdr_comp, hdr_qr]).copy()
                
                if scrubbed_dataframe.empty:
                    st.error("Spreadsheet ingestion terminated: File configuration matrix contains no usable information blocks.")
                else:
                    os.makedirs(ui_disk_path, exist_ok=True)
                    loaded_logo_obj = Image.open(input_logo)

                    # Build high-speed RAM storage tracking registry map for input assets
                    system_qr_ram_cache = {}
                    for file_pointer in input_bulk_qrs:
                        standard_filename_key = str(file_pointer.name).strip().lower()
                        system_qr_ram_cache[standard_filename_key] = file_pointer
                        # Clean variant additions to protect lookups against trailing index strings
                        stripped_variant = re.sub(r'\s*\(\d+\)', '', standard_filename_key)
                        system_qr_ram_cache[stripped_variant] = file_pointer

                    batch_progressbar = st.progress(0)
                    batch_status_card = st.empty()
                    total_work_items = len(scrubbed_dataframe)
                    st.session_state.total_compiled = 0

                    compressed_binary_stream = io.BytesIO()

                    with zipfile.ZipFile(compressed_binary_stream, "w", zipfile.ZIP_DEFLATED) as zip_envelope:
                        for row_idx, row_values in scrubbed_dataframe.iterrows():
                            # Safely cast spreadsheet strings to localized variables
                            val_company = str(row_values.get(hdr_comp, "")).strip()
                            val_product = str(row_values.get(hdr_prod, "")).strip()
                            val_client = str(row_values.get(hdr_client, "")).strip()
                            val_standard = str(row_values.get(hdr_std, "")).strip()
                            val_qr_name = str(row_values.get(hdr_qr, "")).strip()

                            if not val_qr_name or val_qr_name.lower() == 'nan':
                                continue

                            batch_status_card.markdown(f"⚙️ *Compiling Vector Layout:* **{st.session_state.total_compiled + 1}/{total_work_items}** — `{val_company[:42]}...`")
                            
                            # Standardize file check queries
                            target_lookup_string = val_qr_name.lower().strip()
                            target_lookup_stripped = re.sub(r'\s*\(\d+\)', '', target_lookup_string)

                            # Locate appropriate key inside RAM cache file dictionary
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

                                # Compile graphic blueprint elements onto white master canvas layout 
                                final_compiled_vector = render_blueprint_compliance_label(
                                    loaded_qr_obj, loaded_logo_obj,
                                    val_company, val_product, val_standard, val_client,
                                    ui_width, ui_height, ui_font_sz
                                )

                                # Generate system-safe string identifiers for disk outputs
                                sanitized_id = val_client.replace('/', '_').replace('\\', '_') if val_client and val_client.lower() != 'nan' else f"Row_{row_idx}"
                                export_file_name = f"Label_{sanitized_id}.jpg"
                                
                                # Write output image path onto system environment drive
                                final_compiled_vector.save(os.path.join(ui_disk_path, export_file_name), "JPEG", quality=95)

                                # Compress and dump file straight into target RAM zip buffer
                                internal_img_ram_buffer = io.BytesIO()
                                final_compiled_vector.save(internal_img_ram_buffer, format="JPEG", quality=95)
                                zip_envelope.writestr(export_file_name, internal_img_ram_buffer.getvalue())

                                st.session_state.total_compiled += 1
                            else:
                                st.warning(f"⚠️ Missing Upload Asset: Database row requires filename `{val_qr_name}` for `{val_company}`, but it was not present in the uploaded selection. Entry skipped.")

                            batch_progressbar.progress((row_idx + 1) / total_work_items)

                    batch_status_card.empty()
                    compressed_binary_stream.seek(0)
                    st.session_state.zip_stream_bytes = compressed_binary_stream.getvalue()
                    st.session_state.is_process_clean = True

            except Exception as system_pipeline_fault:
                st.error(f"Critical Runtime Exception Error: {str(system_pipeline_fault)}")

    # Display operational metrics metrics upon clean compilation completion runs
    if st.session_state.is_process_clean and st.session_state.zip_stream_bytes:
        st.markdown(
            f"""
            <div class='success-panel'>
                <h4 style='color: #15A34A; margin-top: 0;'>✅ Automated Multi-Field Pipeline Generation Complete</h4>
                <p style='color: #1F2937; margin-bottom: 0;'>Processed and compiled <b>{st.session_state.total_compiled}</b> corporate compliance certificates. Formatted image vectors are saved locally to: <code>{ui_disk_path}</code></p>
            </div>
        """,
            unsafe_allow_html=True,
        )

        st.download_button(
            label="📥 DOWNLOAD ALL LABELS AS COMPRESSED ARCHIVE (ZIP)",
            data=st.session_state.zip_stream_bytes,
            file_name="esm_batch_labels.zip",
            mime="application/zip",
            use_container_width=True
        )