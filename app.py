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
    """Deep scans rows of the uploaded file to locate the correct metadata starting grid

    even if template rows block the top of the worksheet sheet.
    """
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
st.markdown("<div class='main-title'>National Standards Mark (ESM) Batch Engine</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>High-Level Official Verification Console & Multi-Field Graphic Assembly Line</div>", unsafe_allow_html=True)

st.sidebar.markdown("### 🎛️ Geometric Canvas Controllers")
ui_width = st.sidebar.slider("Label Output Pixel Width", 800, 2400, 1200, step=100)
ui_height = st.sidebar.slider("Label Output Pixel Height", 500, 1500, 800, step=100)
ui_font_sz = st.sidebar.slider("Base Label Font Size", 16, 60, 36, step=2)

st.sidebar.markdown("---")
ui_disk_path = st.sidebar.text_input("Local Output Directory Target Path", value="output/esm_labels/")

tab_production, tab_sandbox = st.tabs(["🚀 Automated Pipeline Room", "🔍 Live Vector Structural Sandbox"])

# 1. LIVE SANDBOX CALIBRATION TAB
with tab_sandbox:
    st.subheader("Isolated Layout Vector Verification")
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
    st.subheader("Automated Execution Configuration Room")
    
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

                                st.session_state.total_compiled += 1

                            batch_progressbar.progress((row_idx + 1) / total_work_items)

                    batch_status_card.empty()
                    compressed_binary_stream.seek(0)
                    st.session_state.zip_stream_bytes = compressed_binary_stream.getvalue()
                    st.session_state.is_process_clean = True

            except Exception as system_pipeline_fault:
                st.error(f"Critical Runtime Exception Error: {str(system_pipeline_fault)}")

    if st.session_state.is_process_clean and st.session_state.zip_stream_bytes:
        st.markdown(
            f"""
            <div class='success-panel'>
                <h4 style='color: #15A34A; margin-top: 0;'>✅ Automated Multi-Field Pipeline Generation Complete</h4>
                <p style='color: #1F2937; margin-bottom: 0;'>Processed and compiled <b>{st.session_state.total_compiled}</b> labels directly into: <code>{ui_disk_path}</code></p>
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