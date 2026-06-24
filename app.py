import io
import os
import re
import textwrap
import zipfile
import platform
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# -------------------------------------------------------------------------
# CONSTANTS
# -------------------------------------------------------------------------
APP_TITLE = "Digital Standards Mark (DSM)"
APP_SUBTITLE = "Unique Client Batch ID Generator"
MAX_HEADER_SCAN_ROWS = 25
MIN_HEADER_MATCHES = 2
PDF_MARGIN_PTS = 54
DEFAULT_OUTPUT_DIR = "output/dsm_labels"

FONT_CANDIDATES = {
    "Windows": ["arialbd.ttf", "arial.ttf"],
    "Linux": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ],
    "Darwin": [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
}

# -------------------------------------------------------------------------
# STYLING
# -------------------------------------------------------------------------
st.set_page_config(
    page_title=f"{APP_TITLE} — {APP_SUBTITLE}",
    page_icon="🇪🇹",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #E0F2FE !important; }
    [data-baseweb="tab-list"], div[data-testid="stTabBar"], .stTabs [role="tablist"] {
        background-color: transparent !important;
        border-bottom: 3px solid #1E40AF !important;
        padding-bottom: 8px !important; gap: 14px !important;
    }
    [data-baseweb="tab"], div[data-testid="stTabBar"] button, .stTabs [role="tab"] {
        background-color: #FFFFFF !important;
        border: 2px solid #000000 !important;
        border-radius: 6px !important;
        padding: 8px 18px !important;
        box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.08) !important;
        transition: all 0.2s ease-in-out !important;
    }
    [data-baseweb="tab"] p, [data-baseweb="tab"] span,
    div[data-testid="stTabBar"] button p, .stTabs [role="tab"] p {
        color: #000000 !important; font-weight: 700 !important; font-size: 16px !important;
    }
    [data-baseweb="tab"]:hover, div[data-testid="stTabBar"] button:hover, .stTabs [role="tab"]:hover {
        border-color: #1D4ED8 !important; background-color: #F1F5F9 !important;
    }
    [aria-selected="true"], [data-baseweb="tab"][aria-selected="true"],
    div[data-testid="stTabBar"] button[aria-selected="true"],
    .stTabs [role="tab"][aria-selected="true"] {
        background-color: #EFF6FF !important;
        border: 2.5px solid #0000FF !important;
        box-shadow: 0px 4px 8px rgba(0, 0, 255, 0.15) !important;
    }
    [aria-selected="true"] p, [data-baseweb="tab"][aria-selected="true"] p,
    div[data-testid="stTabBar"] button[aria-selected="true"] p,
    .stTabs [role="tab"][aria-selected="true"] p {
        color: #0000FF !important; font-weight: 700 !important;
    }
    .shaded-header-panel {
        background-color: #1E40AF !important; color: #FFFFFF !important;
        font-size: 1.8rem !important; font-weight: bold !important;
        padding: 0.75rem 1.5rem !important; border-radius: 4px !important;
        margin: 1.5rem 0 !important; display: inline-block !important;
        box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.15);
    }
    .main-title-container {
        background-color: #0000FF !important; padding: 1.5rem !important;
        border-radius: 4px !important; text-align: center !important;
        margin-bottom: 2rem !important;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    .title-line-primary {
        font-size: 3.2rem !important; color: #FFFFFF !important;
        font-weight: 700 !important; margin: 0 !important; padding: 0 !important;
        line-height: 1.2 !important; letter-spacing: 0.05rem !important;
    }
    .title-line-secondary {
        font-size: 2.1rem !important; color: #FFFFFF !important;
        font-weight: 500 !important; margin: 0.4rem 0 0 0 !important;
        padding: 0 !important; letter-spacing: 0.02rem !important;
    }
    [data-testid="stWidgetLabel"] p {
        font-size: 14px !important; font-weight: bold !important; color: #1F2937 !important;
    }
    .sub-title {
        font-size: 1.1rem !important; color: #1E3A8A !important; font-weight: 500;
        margin-bottom: 2rem; text-align: center;
    }
    .success-panel {
        border-radius: 8px; padding: 1.5rem; background-color: #F0FDF4;
        border-left: 6px solid #16A34A; margin-top: 1.5rem;
    }
    .error-panel {
        border-radius: 8px; padding: 1.5rem; background-color: #FEF2F2;
        border-left: 6px solid #DC2626; margin-top: 1.5rem;
    }
    </style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------------------
# FONT RESOLUTION
# -------------------------------------------------------------------------
def resolve_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    system = platform.system()
    candidates = FONT_CANDIDATES.get(system, [])
    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except (IOError, OSError):
            continue
    for name in ["DejaVuSans-Bold", "LiberationSans-Bold", "FreeSansBold", "Arial-Bold", "Arial"]:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


# -------------------------------------------------------------------------
# LABEL RENDERING
# -------------------------------------------------------------------------
def _draw_border(draw: ImageDraw.Draw, width: int, height: int, thickness: int) -> None:
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(0, 0, 0), width=thickness)


def _draw_qr_code(canvas_img: Image.Image, qr_img: Optional[Image.Image], x: int, y: int, dim: int) -> None:
    if qr_img is None:
        return
    qr_clean = qr_img.convert("RGBA").resize((dim, dim), Image.Resampling.LANCZOS)
    canvas_img.paste(qr_clean, (x, y), qr_clean)


def render_compliance_label(
    qr_img: Optional[Image.Image],
    logo_img: Optional[Image.Image],
    company: str,
    product: str,
    standard: str,
    client: str,
    width: int,
    height: int,
    base_font_size: int
) -> Image.Image:
    label = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(label)

    border_thickness = max(3, int(height * 0.008))
    _draw_border(draw, width, height, border_thickness)

    # QR fills the full height between "red lines"
    qr_dim = int(height * 0.88)
    qr_x = border_thickness + int(width * 0.025)
    qr_y = (height - qr_dim) // 2

    # Right column
    gap = int(width * 0.03)
    right_x_start = qr_x + qr_dim + gap
    right_x_end = width - (border_thickness + int(width * 0.025))
    right_width = right_x_end - right_x_start
    right_center = right_x_start + (right_width // 2)

    _draw_qr_code(label, qr_img, qr_x, qr_y, qr_dim)

    # Prepare metadata
    meta_items_raw = []
    if product and str(product).lower() != "nan":
        meta_items_raw.append(str(product).upper())
    if standard and str(standard).lower() != "nan":
        clean_std = re.sub(r"^STANDARD\s+R/NO:\s*", "", str(standard), flags=re.IGNORECASE).strip().upper()
        if clean_std:
            meta_items_raw.append(clean_std)
    if client and str(client).lower() != "nan":
        clean_client = re.sub(r"^CLIENT\s+CODE:\s*", "", str(client), flags=re.IGNORECASE).strip().upper()
        if clean_client:
            meta_items_raw.append(clean_client)

    company_text = str(company).upper()

    # Font sizes: scale with QR height for guaranteed visibility
    header_font_size = int(qr_dim * 0.10)
    header_font_size = max(header_font_size, int(base_font_size * 2.5))
    header_font = resolve_font(header_font_size, bold=True)

    meta_font_size = int(header_font_size * 0.75)
    meta_font_size = max(meta_font_size, int(base_font_size * 2.0))
    meta_font = resolve_font(meta_font_size, bold=True)
    meta_bold_font = resolve_font(int(meta_font_size * 1.05), bold=True)

    wrap_limit = max(8, int(right_width / (header_font_size * 0.6)))

    # === Company Name (top, flush with QR top) ===
    company_lines = textwrap.wrap(company_text, width=wrap_limit)
    header_total_h = 0
    y_cursor = qr_y
    for line in company_lines:
        bbox = draw.textbbox((0, 0), line, font=header_font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        draw.text((right_center - (line_w // 2), y_cursor), line, fill=(0, 0, 0), font=header_font)
        spacing = line_h + 4
        y_cursor += spacing
        header_total_h += spacing

    # === Metadata (bottom, flush with QR bottom) ===
    meta_fonts = []
    meta_items = []
    for i, text in enumerate(meta_items_raw):
        meta_fonts.append(meta_bold_font if i == 0 else meta_font)
        meta_items.append(text)

    line_spacing = 6
    stack_height = 0
    for text, font in zip(meta_items, meta_fonts):
        bbox = draw.textbbox((0, 0), text, font=font)
        stack_height += (bbox[3] - bbox[1]) + line_spacing

    meta_y_start = (qr_y + qr_dim) - stack_height

    y_cursor = meta_y_start
    for text, font in zip(meta_items, meta_fonts):
        text = text.strip()
        if not text:
            continue
        bbox = draw.textbbox((0, 0), text, font=font)
        item_w = bbox[2] - bbox[0]
        item_h = bbox[3] - bbox[1]
        draw.text((right_center - (item_w // 2), y_cursor), text, fill=(0, 0, 0), font=font)
        y_cursor += item_h + line_spacing

    # === Logo (middle, fill remaining space) ===
    available_top = qr_y + header_total_h + int(qr_dim * 0.02)
    available_bottom = meta_y_start - int(qr_dim * 0.02)
    available_height = available_bottom - available_top
    available_width = right_width

    if logo_img is not None and available_height > 20 and available_width > 20:
        logo_ratio = logo_img.width / logo_img.height
        avail_ratio = available_width / available_height

        if logo_ratio > avail_ratio:
            logo_w = int(available_width * 0.75)
            logo_h = int(logo_w / logo_ratio)
        else:
            logo_h = int(available_height * 0.75)
            logo_w = int(logo_h * logo_ratio)

        logo_x = right_x_start + (available_width - logo_w) // 2
        logo_y = available_top + (available_height - logo_h) // 2

        logo_clean = logo_img.convert("RGBA").resize((logo_w, logo_h), Image.Resampling.LANCZOS)
        label.paste(logo_clean, (logo_x, logo_y), logo_clean)

    return label


# -------------------------------------------------------------------------
# EXCEL PARSING
# -------------------------------------------------------------------------
def _clean_token(val) -> str:
    return re.sub(r"[^a-z0-9]", "", str(val).lower().strip())


def _find_header_row(df: pd.DataFrame, max_rows: int = MAX_HEADER_SCAN_ROWS) -> int:
    target_keywords = {"companyname", "company", "producttype", "product", "clientcode", "standardrno", "qrfilename"}
    for idx in range(min(max_rows, len(df))):
        row_tokens = [_clean_token(cell) for cell in df.iloc[idx].dropna()]
        matches = [tok for tok in row_tokens if any(key in tok for key in target_keywords)]
        if len(matches) >= MIN_HEADER_MATCHES:
            return idx
    return 0


def _resolve_header(norm_mapping: Dict[str, str], variants: List[str], fallback: str) -> str:
    for variant in variants:
        cleaned = _clean_token(variant)
        if cleaned in norm_mapping:
            return norm_mapping[cleaned]
        for native_col in norm_mapping:
            if cleaned in native_col or native_col in cleaned:
                return norm_mapping[native_col]
    return fallback


def parse_excel_workbook(workbook_buffer: io.BytesIO) -> Tuple[pd.DataFrame, Dict[str, str]]:
    try:
        raw_df = pd.read_excel(workbook_buffer, header=None)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {e}")

    if raw_df.empty:
        raise ValueError("Excel file appears to be empty")

    header_row = _find_header_row(raw_df)

    workbook_buffer.seek(0)
    if header_row > 0:
        df = pd.read_excel(workbook_buffer, skiprows=header_row)
    else:
        df = pd.read_excel(workbook_buffer)

    df.columns = [str(c).strip() for c in df.columns]
    norm_mapping = {_clean_token(col): col for col in df.columns}

    schema = {
        "company": _resolve_header(norm_mapping, ["company name", "company_name", "company"], "Company Name"),
        "product": _resolve_header(norm_mapping, ["product type", "product_type", "product"], "Product Type"),
        "client": _resolve_header(norm_mapping, ["client code", "client_code", "client"], "Client Code"),
        "standard": _resolve_header(norm_mapping, ["standard r/n", "standard r/no", "standard_rn", "standard"], "Standard R/No"),
        "qr": _resolve_header(norm_mapping, ["qr filename", "qr_filename", "qr file"], "QR Filename"),
    }

    missing = []
    if schema["company"] not in df.columns:
        missing.append("company")
    if schema["qr"] not in df.columns:
        missing.append("qr")

    if missing:
        available = ", ".join([f"'{c}'" for c in df.columns])
        raise KeyError(f"Failed to locate mandatory columns: {missing}. Detected headers: {available}")

    return df, schema


# -------------------------------------------------------------------------
# SECURITY
# -------------------------------------------------------------------------
def sanitize_output_path(user_path: str, base_dir: str = ".") -> str:
    base = Path(base_dir).resolve()
    target = (base / user_path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError(f"Invalid output path: '{user_path}'. Path must be within the application directory.")
    return str(target)


def validate_file_size(file_obj, max_mb: int = 50) -> bool:
    if hasattr(file_obj, "size") and file_obj.size > max_mb * 1024 * 1024:
        return False
    return True


# -------------------------------------------------------------------------
# QR CACHE
# -------------------------------------------------------------------------
def build_qr_cache(uploaded_files: List) -> Dict[str, bytes]:
    cache: Dict[str, bytes] = {}
    for fp in uploaded_files:
        if not validate_file_size(fp):
            st.warning(f"File {fp.name} exceeds size limit and was skipped.")
            continue
        name_lower = str(fp.name).strip().lower()
        base_name = os.path.splitext(name_lower)[0]
        fp.seek(0)
        img_bytes = fp.read()
        cache[name_lower] = img_bytes
        cache[base_name] = img_bytes
        stripped = re.sub(r"\s*\(\d+\)", "", base_name).strip()
        if stripped != base_name:
            cache[stripped] = img_bytes
    return cache


def find_qr_image(qr_filename: str, cache: Dict[str, bytes]) -> Optional[bytes]:
    if not qr_filename or str(qr_filename).lower() == "nan":
        return None
    lookup = str(qr_filename).strip().lower()
    base_lookup = os.path.splitext(lookup)[0]
    candidates = [
        lookup, base_lookup,
        lookup + ".png", lookup + ".jpg", lookup + ".jpeg",
        base_lookup + ".png", base_lookup + ".jpg", base_lookup + ".jpeg",
    ]
    for candidate in candidates:
        if candidate in cache:
            return cache[candidate]
    return None


# -------------------------------------------------------------------------
# PDF GENERATION
# -------------------------------------------------------------------------
def add_label_to_pdf(pdf_canvas: canvas.Canvas, label_img: Image.Image, page_size: Tuple[float, float] = letter) -> None:
    page_w, page_h = page_size
    max_w = page_w - (PDF_MARGIN_PTS * 2)
    max_h = page_h - (PDF_MARGIN_PTS * 2)
    scale = min(max_w / label_img.width, max_h / label_img.height)
    draw_w = label_img.width * scale
    draw_h = label_img.height * scale
    x_offset = (page_w - draw_w) / 2
    y_offset = (page_h - draw_h) / 2
    img_buffer = io.BytesIO()
    label_img.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    pdf_img = ImageReader(img_buffer)
    pdf_canvas.drawImage(pdf_img, x_offset, y_offset, width=draw_w, height=draw_h)
    pdf_canvas.showPage()


# -------------------------------------------------------------------------
# BATCH PROCESSING
# -------------------------------------------------------------------------
def process_batch(
    df: pd.DataFrame,
    schema: Dict[str, str],
    logo_img: Image.Image,
    qr_cache: Dict[str, bytes],
    output_dir: str,
    label_width: int,
    label_height: int,
    font_size: int,
    progress_bar,
    status_text
) -> Tuple[int, bytes, bytes]:
    os.makedirs(output_dir, exist_ok=True)

    hdr_comp = schema["company"]
    hdr_prod = schema["product"]
    hdr_client = schema["client"]
    hdr_std = schema["standard"]
    hdr_qr = schema["qr"]

    valid_df = df.dropna(subset=[hdr_comp, hdr_qr]).copy()
    total = len(valid_df)

    if total == 0:
        return 0, b"", b""

    zip_buffer = io.BytesIO()
    pdf_buffer = io.BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=letter)

    processed = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, (_, row) in enumerate(valid_df.iterrows()):
            company = str(row.get(hdr_comp, "")).strip()
            product = str(row.get(hdr_prod, "")).strip()
            client = str(row.get(hdr_client, "")).strip()
            standard = str(row.get(hdr_std, "")).strip()
            qr_name = str(row.get(hdr_qr, "")).strip()

            if not qr_name or qr_name.lower() == "nan" or company.lower() == "nan":
                progress_bar.progress((idx + 1) / total)
                continue

            status_text.markdown(f"⚙️ *Processing:* **{processed + 1}** — `{company[:50]}...`")

            qr_bytes = find_qr_image(qr_name, qr_cache)
            if qr_bytes is None:
                st.warning(f"QR image not found for row {idx + 1}: '{qr_name}' — skipping.")
                progress_bar.progress((idx + 1) / total)
                continue

            try:
                qr_img = Image.open(io.BytesIO(qr_bytes))
            except Exception as e:
                st.warning(f"Invalid QR image for row {idx + 1}: {e} — skipping.")
                progress_bar.progress((idx + 1) / total)
                continue

            try:
                label = render_compliance_label(
                    qr_img, logo_img, company, product, standard, client,
                    label_width, label_height, font_size
                )
            except Exception as e:
                st.error(f"Failed to render label for '{company}': {e}")
                progress_bar.progress((idx + 1) / total)
                continue

            safe_id = re.sub(r"[^\w\-]", "_", client if client and client.lower() != "nan" else f"row_{idx}")
            filename = f"Label_{safe_id}.jpg"
            filepath = os.path.join(output_dir, filename)

            try:
                label.save(filepath, "JPEG", quality=95)
            except Exception as e:
                st.warning(f"Failed to save {filename}: {e}")

            img_buffer = io.BytesIO()
            label.save(img_buffer, format="JPEG", quality=95)
            zf.writestr(filename, img_buffer.getvalue())

            add_label_to_pdf(pdf, label)

            processed += 1
            progress_bar.progress((idx + 1) / total)

    pdf.save()
    zip_buffer.seek(0)
    pdf_buffer.seek(0)

    return processed, zip_buffer.getvalue(), pdf_buffer.getvalue()


# -------------------------------------------------------------------------
# INTERFACE
# -------------------------------------------------------------------------
st.markdown(f"""
    <div class="main-title-container">
        <div class="title-line-primary">{APP_TITLE}</div>
        <div class="title-line-secondary">{APP_SUBTITLE}</div>
    </div>
""", unsafe_allow_html=True)

st.markdown('<div class="sub-title">High-Level Official Verification Console & Multi-Field Graphic Assembly Line</div>', unsafe_allow_html=True)

st.sidebar.markdown("### 🎛️ Geometric Canvas Controllers")
ui_width = st.sidebar.slider("Label Width (px)", 800, 2400, 1200, step=100)
ui_height = st.sidebar.slider("Label Height (px)", 500, 1500, 680, step=20)
ui_font_sz = st.sidebar.slider("Base Font Size", 16, 120, 32, step=2)

st.sidebar.markdown("---")
ui_disk_path = st.sidebar.text_input("Output Directory", value=DEFAULT_OUTPUT_DIR, help="Relative path within the application directory. Path traversal is blocked for security.")

for key, default in {"zip_bytes": None, "pdf_bytes": None, "process_ok": False, "compiled_count": 0}.items():
    if key not in st.session_state:
        st.session_state[key] = default

tab_production, tab_sandbox = st.tabs(["🚀 Automated Pipeline", "🔍 Layout Sandbox"])

# -------------------------------------------------------------------------
# SANDBOX TAB
# -------------------------------------------------------------------------
with tab_sandbox:
    st.markdown("<div class='shaded-header-panel'>Layout Preview & Calibration</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        sb_company = st.text_input("Company Name", "CASTEL WINERY PLC", key="sb_company")
        sb_product = st.text_input("Product Type", "ACACIA MEDIUM SWEET RED WINE", key="sb_product")
        sb_standard = st.text_input("Standard Reference", "CES 71:2021", key="sb_standard")
        sb_client = st.text_input("Client Code", "ESML-CAMSRW-CA401548", key="sb_client")
    with col2:
        sb_logo = st.file_uploader("Upload Logo", type=["png", "jpg", "jpeg"], key="sb_logo")
        sb_qr = st.file_uploader("Upload QR Code", type=["png", "jpg", "jpeg"], key="sb_qr")

    if st.button("Generate Preview", type="secondary"):
        if sb_logo and sb_qr:
            try:
                logo = Image.open(sb_logo)
                qr = Image.open(sb_qr)
                preview = render_compliance_label(
                    qr, logo, sb_company, sb_product, sb_standard, sb_client,
                    ui_width, ui_height, ui_font_sz
                )
                st.image(preview, caption="Label Preview", use_container_width=True)
            except Exception as e:
                st.error(f"Preview generation failed: {e}")
        else:
            st.error("Please upload both logo and QR code images.")

# -------------------------------------------------------------------------
# PRODUCTION TAB
# -------------------------------------------------------------------------
with tab_production:
    st.markdown("<div class='shaded-header-panel'>Batch Production Configuration</div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        input_excel = st.file_uploader("1. Excel Registry File", type=["xlsx", "xls"], help="Must contain columns: Company Name, QR Filename (fuzzy matching supported)")
    with c2:
        input_logo = st.file_uploader("2. Standard Mark", type=["png", "jpg", "jpeg"], help="National standards mark or certification logo")

    input_bulk_qrs = st.file_uploader("3. QR Code Images (batch upload)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, help="Upload all QR images referenced in the Excel file")

    if st.button("Execute Batch Pipeline", type="primary"):
        if not input_excel or not input_logo or not input_bulk_qrs:
            st.error("Please provide all required inputs: Excel file, logo, and QR code images.")
        else:
            try:
                safe_output_dir = sanitize_output_path(ui_disk_path)
                df, schema = parse_excel_workbook(input_excel)
                st.info(f"Parsed {len(df)} rows. Detected headers: {list(schema.values())}")

                logo_img = Image.open(input_logo)
                qr_cache = build_qr_cache(input_bulk_qrs)
                st.info(f"Loaded {len(qr_cache)} unique QR image variants into cache.")

                progress = st.progress(0)
                status = st.empty()

                count, zip_data, pdf_data = process_batch(
                    df, schema, logo_img, qr_cache,
                    safe_output_dir, ui_width, ui_height, ui_font_sz,
                    progress, status
                )

                status.empty()

                if count > 0:
                    st.session_state.zip_bytes = zip_data
                    st.session_state.pdf_bytes = pdf_data
                    st.session_state.compiled_count = count
                    st.session_state.process_ok = True
                    st.success(f"✅ Successfully generated {count} labels!")
                else:
                    st.warning("No valid labels could be generated. Check your data and QR image filenames.")
                    st.session_state.process_ok = False

            except ValueError as e:
                st.error(f"Validation Error: {e}")
            except KeyError as e:
                st.error(f"Column Error: {e}")
            except Exception as e:
                st.error(f"Unexpected Error: {e}")
                import traceback
                st.code(traceback.format_exc())

    if st.session_state.process_ok and st.session_state.zip_bytes:
        st.markdown(f"""
            <div class="success-panel">
                <h4 style="color: #15A34A; margin-top: 0;">✅ Batch Generation Complete</h4>
                <p style="color: #1F2937; margin-bottom: 0;">Processed <b>{st.session_state.compiled_count}</b> compliance labels.</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        dl1, dl2 = st.columns(2)

        with dl1:
            st.download_button(
                label="📥 Download ZIP Archive",
                data=st.session_state.zip_bytes,
                file_name="dsm_batch_labels.zip",
                mime="application/zip",
                use_container_width=True
            )
        with dl2:
            st.download_button(
                label="📄 Download PDF Register",
                data=st.session_state.pdf_bytes,
                file_name="dsm_batch_register.pdf",
                mime="application/pdf",
                use_container_width=True
            )