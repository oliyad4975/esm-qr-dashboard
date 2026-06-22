import io
import os
import re
import zipfile
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# -------------------------------------------------------------------------
# STYLING & VIEWPORT CONFIGURATION (NORMAL BLUE WITH GREEN TITLE OVERRIDE)
# -------------------------------------------------------------------------
st.set_page_config(
    page_title="National Standards Mark Batch Production Engine",
    page_icon="🇪🇹",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    /* Global Application Canvas Base Background */
    .stApp {
        background-color: #1E3A8A !important;
    }
    
    /* Green Title Typography Override for High Contrast Legibility */
    .main-title { 
        font-size: 2.6rem !important; 
        color: #4ADE80 !important; 
        font-weight: 800; 
        letter-spacing: -0.05rem; 
        padding-top: 1rem;
    }
    
    /* Sub-title Typography Parameters */
    .sub-title { 
        font-size: 1.1rem !important; 
        color: #F8FAFC !important; 
        margin-bottom: 2rem; 
    }
    
    /* Tab Label Typography and Global Content Overrides */
    .stTabs [data-baseweb="tab"] {
        color: #FFFFFF !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #4ADE80 !important;
    }
    
    /* Ingestion Box & Metadata Label Text Colors */
    .stMarkdown, p, label, .stSlider, [data-testid="stWidgetLabel"] p, [data-testid="stMarkdownContainer"] p {
        color: #FFFFFF !important;
    }
    
    /* Sidebar Surface Container Formatting */
    section[data-testid="stSidebar"] {
        background-color: #1E293B !important;
    }
    section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] p {
        color: #FFFFFF !important;
    }
    
    /* System Pipeline Success Status Alert Box */
    .success-panel { 
        border-radius: 8px; 
        padding: 1.5rem; 
        background-color: #064E3B; 
        border-left: 6px solid #10B981; 
        margin-top: 1.5rem; 
    }
    </style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------------
# GRAPHIC RENDER ENGINE: YELLOW-FRAME PROPORTIONAL GEOMETRY
# -------------------------------------------------------------------------
def render_blueprint_compliance_label(
    qr_raw_img, logo_raw_img, company_txt, product_txt, standard_txt, client_txt, c_width, c_height, base_f_size):
    """Compiles assets into a dual-column layout where the QR Code dimensions
    strictly mirror the yellow square layout reference (72% of total canvas height),
    providing clean spatial balance with the centered text and logo column.
    """
    label_canvas = Image.new("RGB", (c_width, c_height), color=(255, 255, 255))
    draw_interface = ImageDraw.Draw(label_canvas)

    qr_target_dim = int(c_height * 0.72)
    qr_x_origin = int(c_width * 0.05)
    qr_y_origin = (c_height - qr_target_dim) // 2
    qr_right_edge = qr_x_origin + qr_target_dim

    try:
        font_header = ImageFont.truetype("arialbd.ttf", base_f_size)
        font_metadata = ImageFont.truetype("arialbd.ttf", int(base_f_size * 0.72))
        font_meta_bold = ImageFont.truetype("arialbd.ttf", int(base_f_size * 0.76))
    except IOError:
        font_header = ImageFont.load_default()
        font_metadata = ImageFont.load_default()
        font_meta_bold = ImageFont.load_default()

    avg_char_width = base_f_size * 0.55
    three_letter_gap = int(3 * avg_char_width)
    text_column_start_x = qr_right_edge + three_letter_gap

    if qr_raw_img:
        qr_clean = qr_raw_img.convert("RGBA").resize((qr_target_dim, qr_target_dim), Image.Resampling.LANCZOS)
        label_canvas.paste(qr_clean, (qr_x_origin, qr_y_origin), qr_clean)

    company_line = str(company_txt).upper().strip()
    
    meta_stack_collection = []
    if product_txt and str(product_txt).lower() != 'nan':
        meta_stack_collection.append((str(product_txt).upper().strip(), font_meta_bold))
        
    if standard_txt and str(standard_txt).lower() != 'nan':
        std_val = str(standard_txt).upper().strip()
        display_std = f"STANDARD R/NO: {std_val}" if "STANDARD" not in std_val else std_val
        meta_stack_collection.append((display_std, font_metadata))
        
    if client_txt and str(client_txt).lower() != 'nan':
        client_val = str(client_txt).upper().strip()
        display_client = f"CLIENT CODE: {client_val}" if "CLIENT" not in client_val else client_val
        meta_stack_collection.append((display_client, font_metadata))

    line_padding = int(base_f_size * 0.22)
    logo_target_dim = int(c_height * 0.415)

    _, _, _, b_comp = draw_interface.textbbox((0, 0), company_line, font=font_header)
    company_block_height = b_comp
    
    meta_block_height = 0
    for info_string, font_style in meta_stack_collection:
        _, _, _, b = draw_interface.textbbox((0, 0), info_string, font=font_style)
        meta_block_height += b + line_padding

    total_right_content_height = company_block_height + line_padding + logo_target_dim + line_padding + meta_block_height
    y_cursor = qr_y_origin + ((qr_target_dim - total_right_content_height) // 2)

    max_measured_text_width = logo_target_dim
    _, _, r_comp, _ = draw_interface.textbbox((0, 0), company_line, font=font_header)
    if r_comp > max_measured_text_width:
        max_measured_text_width = r_comp
        
    for info_string, font_style in meta_stack_collection:
        _, _, r_meta, _ = draw_interface.textbbox((0, 0), info_string, font=font_style)
        if r_meta > max_measured_text_width:
            max_measured_text_width = r_meta

    text_layout_center_x = text_column_start_x + (max_measured_text_width // 2)

    left, top, right, bottom = draw_interface.textbbox((0, 0), company_line, font=font_header)
    line_w = right - left
    draw_interface.text((text_layout_center_x - (line_w // 2), y_cursor), company_line, fill=(0, 0, 0), font=font_header)
    y_cursor += company_block_height + line_padding

    if logo_raw_img:
        logo_clean = logo_raw_img.convert("RGBA").resize((logo_target_dim, logo_target_dim), Image.Resampling.LANCZOS)
        logo_x_pos = text_layout_center_x - (logo_target_dim // 2)
        label_canvas.paste(logo_clean, (logo_x_pos, y_cursor), logo_clean)
        y_cursor += logo_target_dim + line_padding

    for info_string, font_style in meta_stack_collection:
        if info_string.strip():
            left, top, right, bottom = draw_interface.textbbox((0, 0), info_string, font=font_style)
            item_w = right - left
            item_h = bottom - top
            draw_interface.text((text_layout_center_x - (item_w // 2), y_cursor), info_string, fill=(0, 0, 0), font=font_style)
            y_cursor += item_h + line_padding

    return label_canvas

# -------------------------------------------------------------------------
# DIRECT STREAMLINED SCHEMATIC EXCEL LINKER
# -------------------------------------------------------------------------
def parse_and_validate_excel(workbook_buffer):
    parsed_df = pd.read_excel(workbook_buffer)
    parsed_df.columns = [str(c).strip() for c in parsed_df.columns]
    
    target_headers = {
        "company": "Company Name",
        "product": "Product Type",
        "client": "Client Code",
        "standard": "Standard R/No",
        "qr": "QR Filename"
    }
    
    for variable_label, explicit_column_name in target_headers.items():
        if explicit_column_name not in parsed_df.columns:
            all_found_headers = ", ".join([f"'{x}'" for x in parsed_df.columns])
            raise KeyError(f"Required structural descriptor column '{explicit_column_name}' was not found.")
            
    return parsed_df, target_headers

# -------------------------------------------------------------------------
# INTERFACE CONTROL DECK
# -------------------------------------------------------------------------
st.markdown("<div class='main-title'>National Standards Mark (ESM) Batch Engine</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>High-Level Official Verification Console & Proportional Vector Assembly Line</div>", unsafe_allow_html=True)

st.sidebar.markdown("### 🎛️ Geometric Canvas Controllers")
ui_width = st.sidebar.slider("Label Output Pixel Width", 800, 2400, 1400, step=100)
ui_height = st.sidebar.slider("Label Output Pixel Height", 500, 1500, 800, step=100)
ui_font_sz = st.sidebar.slider("Base Label Font Size", 16, 60, 34, step=2)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📄 Output Document Formatter")
ui_format_type = st.sidebar.selectbox(
    "Target Document Architecture Format",
    options=["Image Asset (JPEG)", "Document Vector (PDF)"],
    index=0
)

st.sidebar.markdown("---")
ui_disk_path = st.sidebar.text_input("Local Environment Output Directory Target Path", value="output/esm_labels/")

tab_production, tab_sandbox = st.tabs(["🚀 Automated Pipeline Room", "🔍 Live Vector Structural Sandbox"])

# 1. LIVE SANDBOX CALIBRATION TAB
with tab_sandbox:
    st.subheader("Isolated Layout Vector Verification")
    
    box_c1, box_c2 = st.columns(2)
    with box_c1:
        sb_company = st.text_input("Corporate Identifier Line", "CASTEL WINERY PLC")
        sb_product = st.text_input("Product Designation Line", "ACACIA MEDIUM SWEET RED WINE")
        sb_standard = st.text_input("Regulatory Protocol Tracking Code", "CES 71:2021")
        sb_client = st.text_input("Registered Enterprise Entity Reference", "ESML-CAMSRW-CA401548")
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
            if "PDF" in ui_format_type:
                pdf_compliant_canvas = preview_image_result.convert("RGB")
                pdf_compliant_canvas.save(isolated_buffer, format="PDF")
                st.download_button("📥 Export Isolated Document (PDF)", data=isolated_buffer.getvalue(), file_name="esm_individual_sample.pdf", mime="application/pdf")
            else:
                preview_image_result.save(isolated_buffer, format="JPEG", quality=95)
                st.download_button("📥 Export Isolated Image (JPG)", data=isolated_buffer.getvalue(), file_name="esm_individual_sample.jpg", mime="image/jpeg")
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
                src_dataframe, computed_headers = parse_and_validate_excel(input_excel)
                
                hdr_comp = computed_headers["company"]
                hdr_prod = computed_headers["product"]
                hdr_client = computed_headers["client"]
                hdr_std = computed_headers["standard"]
                hdr_qr = computed_headers["qr"]

                scrubbed_dataframe = src_dataframe.dropna(subset=[hdr_comp, hdr_qr]).copy()
                
                if scrubbed_dataframe.empty:
                    st.error("Spreadsheet Ingestion Failed.")
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

                            if not val_qr_name or val_qr_name.lower() == 'nan':
                                continue

                            batch_status_card.markdown(f"⚙️ *Compiling Vector Layout:* **{st.session_state.total_compiled + 1}/{total_work_items}**")
                            
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
                                
                                internal_img_ram_buffer = io.BytesIO()
                                
                                if "PDF" in ui_format_type:
                                    export_file_name = f"Label_{sanitized_id}.pdf"
                                    pdf_version = final_compiled_vector.convert("RGB")
                                    pdf_version.save(os.path.join(ui_disk_path, export_file_name), "PDF")
                                    pdf_version.save(internal_img_ram_buffer, format="PDF")
                                else:
                                    export_file_name = f"Label_{sanitized_id}.jpg"
                                    final_compiled_vector.save(os.path.join(ui_disk_path, export_file_name), "JPEG", quality=95)
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
        archive_name = "esm_batch_labels_pdf.zip" if "PDF" in ui_format_type else "esm_batch_labels_jpg.zip"
        st.markdown(
            f"""
            <div class='success-panel'>
                <h4 style='color: #A7F3D0; margin-top: 0;'>✅ Automated Multi-Field Pipeline Generation Complete</h4>
                <p style='color: #F8FAFC; margin-bottom: 0;'>Processed and compiled <b>{st.session_state.total_compiled}</b> compliance vectors formatted as <b>{ui_format_type}</b>.</p>
            </div>
        """,
            unsafe_allow_html=True,
        )

        st.download_button(
            label=f"📥 DOWNLOAD ALL LABELS AS COMPRESSED {ui_format_type.upper()} ARCHIVE (ZIP)",
            data=st.session_state.zip_stream_bytes,
            file_name=archive_name,
            mime="application/zip",
            use_container_width=True
        )