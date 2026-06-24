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

# -------------------------------------------------------------------------
# CONSTANTS & CONFIGURATION
# -------------------------------------------------------------------------
APP_TITLE = "Digital Standards Mark (DSM)"
APP_SUBTITLE = "Unique Client Batch ID Generator"
MIN_PILLOW_VERSION = (9, 1, 0)
MAX_HEADER_SCAN_ROWS = 25
MIN_HEADER_MATCHES = 2
PDF_MARGIN_PTS = 54  # 0.75 inch margin
DEFAULT_OUTPUT_DIR = "output/dsm_labels"
SUPPORTED_IMAGE_EXTS = [".png", ".jpg", ".jpeg"]

# Cross-platform font resolution
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
# STYLING & VIEWPORT CONFIGURATION
# -------------------------------------------------------------------------
st.set_page_config(
    page_title=f"{APP_TITLE} — {APP_SUBTITLE}",
    page_icon="🇪🇹",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
    /* Main Dashboard Background */
    [data-testid="stAppViewContainer"] {
        background-color: #E0F2FE !important;
    }

    /* Tab Controller */
    [data-baseweb="tab-list"], 
    div[data-testid="stTabBar"], 
    .stTabs [role="tablist"] {
        background-color: transparent !important;
        border-bottom: 3px solid #1E40AF !important;
        padding-bottom: 8px !important;
        gap: 14px !important;
    }

    /* Inactive Tab State */
    [data-baseweb="tab"], 
    div[data-testid="stTabBar"] button, 
    .stTabs [role="tab"] {
        background-color: #FFFFFF !important;
        border: 2px solid #000000 !important;
        border-radius: 6px !important;
        padding: 8px 18px !important;
        box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.08) !important;
        transition: all 0.2s ease-in-out !important;
    }

    [data-baseweb="tab"] p, [data-baseweb="tab"] span,
    div[data-testid="stTabBar"] button p, div[data-testid="stTabBar"] button span,
    .stTabs [role="tab"] p, .stTabs [role="tab"] span {
        color: #000000 !important;
        font-weight: 700 !important;
        font-size: 16px !important;
    }

    [data-baseweb="tab"]:hover, 
    div[data-testid="stTabBar"] button:hover, 
    .stTabs [role="tab"]:hover {
        border-color: #1D4ED8 !important;
        background-color: #F1F5F9 !important;
    }

    /* Active Tab State */
    [aria-selected="true"], 
    [data-baseweb="tab"][aria-selected="true"], 
    div[data-testid="stTabBar"] button[aria-selected="true"],
    .stTabs [role="tab"][aria-selected="true"] {
        background-color: #EFF6FF !important;
        border: 2.5px solid #0000FF !important;
        box-shadow: 0px 4px 8px rgba(0, 0, 255, 0.15) !important;
    }

    [aria-selected="true"] p, [aria-selected="true"] span,
    [data-baseweb="tab"][aria-selected="true"] p,
    div[data-testid="stTabBar"] button[aria-selected="true"] p,
    .stTabs [role="tab"][aria-selected="true"] p {
        color: #0000FF !important;
        font-weight: 700 !important;
    }

    .shaded-header-panel {
        background-color: #1E40AF !important;
        color: #FFFFFF !important;
        font-size: 1.8rem !important;
        font-weight: bold !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 4px !important;
        margin: 1.5rem 0 !important;
        display: inline-block !important;
        box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.15);
    }

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

    .success-panel {
        border-radius: 8px;
        padding: 1.5rem;
        background-color: #F0FDF4;
        border-left: 6px solid #16A34A;
        margin-top: 1.5rem;
    }

    .error-panel {
        border-radius: 8px;
        padding: 1.5rem;
        background-color: #FEF2F2;
        border-left: 6px solid #DC2626;
        margin-top: 1.5rem;
    }
    </style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------------------
# FONT RESOLUTION ENGINE
# -------------------------------------------------------------------------
def resolve_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """
    Cross-platform font resolver. Tries OS-specific candidates first,
    then falls back to default.

    Args:
        size: Font size in pixels
        bold: Whether to prefer bold weight

    Returns:
        PIL ImageFont instance
    """
    system = platform.system()
    candidates = FONT_CANDIDATES.get(system, [])

    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except (IOError, OSError):
            continue

    # Final fallback: try common names without path
    for name in ["DejaVuSans-Bold", "LiberationSans-Bold", "FreeSansBold", "Arial-Bold", "Arial"]:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue

    return ImageFont.load_default()


# -------------------------------------------------------------------------
# LABEL RENDERING ENGINE
# -------------------------------------------------------------------------
def _draw_border(draw: ImageDraw.Draw, width: int, height: int, thickness: int) -> None:
    """Draw enclosing bounding box border."""
    draw.rectangle(
        [(0, 0), (width - 1, height - 1)],
        outline=(0, 0, 0),
        width=thickness
    )


def _draw_qr_code(
    canvas_img: Image.Image,
    qr_img: Optional[Image.Image],
    x: int,
    y: int,
    dim: int
) -> None:
    """Render QR code onto label canvas."""
    if qr_img is None:
        return
    qr_clean = qr_img.convert("RGBA").resize((dim, dim), Image.Resampling.LANCZOS)
    canvas_img.paste(qr_clean, (x, y), qr_clean)


def _draw_header_block(
    draw: ImageDraw.Draw,
    company_text: str,
    font: ImageFont.FreeTypeFont,
    center_x: int,
    start_y: int,
    wrap_width: int,
    max_height: int
) -> Tuple[int, int]:
    """
    Draw company header text block.

    Returns:
        Tuple of (final_y_position, total_header_height)
    """
    lines = textwrap.wrap(str(company_text).upper(), width=wrap_width)
    y_cursor = start_y
    total_height = 0

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]

        # Safety check: don't overflow allocated space
        if y_cursor + line_h > start_y + max_height:
            break

        draw.text((center_x - (line_w // 2), y_cursor), line, fill=(0, 0, 0), font=font)
        spacing = line_h + int(max_height * 0.02)
        y_cursor += spacing
        total_height += spacing

    return y_cursor, total_height


def _draw_logo(
    canvas_img: Image.Image,
    logo_img: Optional[Image.Image],
    center_x: int,
    y_pos: int,
    target_dim: int
) -> None:
    """Render certification logo centered at specified position."""
    if logo_img is None or target_dim <= 0:
        return
    logo_clean = logo_img.convert("RGBA").resize((target_dim, target_dim), Image.Resampling.LANCZOS)
    x_pos = center_x - (target_dim // 2)
    canvas_img.paste(logo_clean, (x_pos, y_pos), logo_clean)


def _draw_metadata_block(
    draw: ImageDraw.Draw,
    metadata_items: List[Tuple[str, ImageFont.FreeTypeFont]],
    center_x: int,
    start_y: int,
    line_spacing: int,
    max_y: int
) -> int:
    """
    Draw metadata text lines.

    Returns:
        Final Y position after drawing
    """
    y_cursor = start_y

    for text, font in metadata_items:
        text = text.strip()
        if not text:
            continue

        bbox = draw.textbbox((0, 0), text, font=font)
        item_w = bbox[2] - bbox[0]
        item_h = bbox[3] - bbox[1]

        # Prevent bottom overflow
        if y_cursor + item_h > max_y:
            break

        draw.text((center_x - (item_w // 2), y_cursor), text, fill=(0, 0, 0), font=font)
        y_cursor += item_h + line_spacing

    return y_cursor


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
    """
    Compile assets into a structured compliance label layout.

    Args:
        qr_img: QR code PIL Image
        logo_img: Logo PIL Image
        company: Company name text
        product: Product type text
        standard: Standard reference number
        client: Client code
        width: Label width in pixels
        height: Label height in pixels
        base_font_size: Base font size (will be scaled up)

    Returns:
        Rendered label as PIL Image
    """
    # Create white canvas
    label = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(label)

    # Draw border
    border_thickness = max(3, int(height * 0.008))
    _draw_border(draw, width, height, border_thickness)

    # Calculate QR dimensions and position
    qr_dim = int(height * 0.86)
    qr_x = border_thickness + int(width * 0.03)
    qr_y = (height - qr_dim) // 2

    # Scale fonts
    scaled_size = int(base_font_size * 1.8)
    font_header = resolve_font(scaled_size, bold=True)
    font_meta = resolve_font(int(scaled_size * 0.85), bold=True)
    font_meta_bold = resolve_font(int(scaled_size * 0.90), bold=True)

    # Calculate right column bounds
    gap = int(scaled_size * 0.7)
    right_x_start = qr_x + qr_dim + gap
    right_x_end = width - (border_thickness + int(width * 0.03))
    right_width = right_x_end - right_x_start
    right_center = right_x_start + (right_width // 2)

    # Text wrap limit
    wrap_limit = max(16, int(right_width / (scaled_size * 0.6)))

    # Draw QR code
    _draw_qr_code(label, qr_img, qr_x, qr_y, qr_dim)

    # Draw header block (company name)
    header_max_h = int(qr_dim * 0.35)  # Allocate max 35% of QR height for header
    _, header_h = _draw_header_block(
        draw, company, font_header, right_center, qr_y, wrap_limit, header_max_h
    )

    # Prepare metadata items
    meta_items: List[Tuple[str, ImageFont.FreeTypeFont]] = []

    if product and str(product).lower() != "nan":
        meta_items.append((str(product).upper(), font_meta_bold))

    if standard and str(standard).lower() != "nan":
        clean_std = re.sub(r"^STANDARD\s+R/NO:\s*", "", str(standard), flags=re.IGNORECASE).strip().upper()
        if clean_std:
            meta_items.append((clean_std, font_meta))

    if client and str(client).lower() != "nan":
        clean_client = re.sub(r"^CLIENT\s+CODE:\s*", "", str(client), flags=re.IGNORECASE).strip().upper()
        if clean_client:
            meta_items.append((clean_client, font_meta))

    # Calculate metadata stack height
    line_spacing = int(qr_dim * 0.015)
    stack_height = sum(
        (draw.textbbox((0, 0), text, font=font)[3] - draw.textbbox((0, 0), text, font=font)[1]) + line_spacing
        for text, font in meta_items
    )

    # Bottom-align metadata with QR bottom edge
    meta_y_start = (qr_y + qr_dim) - stack_height

    # Calculate logo space and position
    available_logo_space = meta_y_start - (qr_y + header_h)
    logo_dim = int(available_logo_space * 0.85)
    max_logo = int(qr_dim * 0.40)
    min_logo = int(qr_dim * 0.25)
    logo_dim = max(min_logo, min(logo_dim, max_logo))

    logo_y = qr_y + header_h + ((available_logo_space - logo_dim) // 2)

    # Draw logo
    _draw_logo(label, logo_img, right_center, logo_y, logo_dim)

    # Draw metadata block
    meta_start_y = max(meta_y_start, logo_y + logo_dim + int(qr_dim * 0.01))
    _draw_metadata_block(
        draw, meta_items, right_center, meta_start_y, line_spacing, qr_y + qr_dim - border_thickness
    )

    return label


# -------------------------------------------------------------------------
# EXCEL PARSING ENGINE
# -------------------------------------------------------------------------
def _clean_token(val) -> str:
    """Normalize cell value for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", str(val).lower().strip())


def _find_header_row(df: pd.DataFrame, max_rows: int = MAX_HEADER_SCAN_ROWS) -> int:
    """
    Scan for header row using fuzzy keyword matching.

    Returns:
        Row index of detected header, or 0 if not found
    """
    target_keywords = {
        "companyname", "company", "producttype", "product",
        "clientcode", "standardrno", "qrfilename"
    }

    for idx in range(min(max_rows, len(df))):
        row_tokens = [_clean_token(cell) for cell in df.iloc[idx].dropna()]
        matches = [tok for tok in row_tokens if any(key in tok for key in target_keywords)]
        if len(matches) >= MIN_HEADER_MATCHES:
            return idx

    return 0


def _resolve_header(
    norm_mapping: Dict[str, str],
    variants: List[str],
    fallback: str
) -> str:
    """Fuzzy header name resolver."""
    for variant in variants:
        cleaned = _clean_token(variant)
        if cleaned in norm_mapping:
            return norm_mapping[cleaned]
        for native_col in norm_mapping:
            if cleaned in native_col or native_col in cleaned:
                return norm_mapping[native_col]
    return fallback


def parse_excel_workbook(workbook_buffer: io.BytesIO) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Adaptive Excel parser with fuzzy header detection.

    Args:
        workbook_buffer: Excel file as BytesIO

    Returns:
        Tuple of (DataFrame, column_mapping_dict)

    Raises:
        KeyError: If mandatory columns cannot be found
        ValueError: If workbook is empty or unreadable
    """
    try:
        raw_df = pd.read_excel(workbook_buffer, header=None)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {e}")

    if raw_df.empty:
        raise ValueError("Excel file appears to be empty")

    header_row = _find_header_row(raw_df)

    # Re-read with correct header
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

    # Validate mandatory columns
    missing = []
    if schema["company"] not in df.columns:
        missing.append("company")
    if schema["qr"] not in df.columns:
        missing.append("qr")

    if missing:
        available = ", ".join([f"\'{c}\'" for c in df.columns])
        raise KeyError(
            f"Failed to locate mandatory columns: {missing}. "
            f"Detected headers: {available}"
        )

    return df, schema


# -------------------------------------------------------------------------
# SECURITY & VALIDATION
# -------------------------------------------------------------------------
def sanitize_output_path(user_path: str, base_dir: str = ".") -> str:
    """
    Prevent path traversal attacks by resolving and validating output path.

    Args:
        user_path: User-provided path string
        base_dir: Allowed base directory

    Returns:
        Sanitized absolute path

    Raises:
        ValueError: If path escapes base directory
    """
    base = Path(base_dir).resolve()
    target = (base / user_path).resolve()

    # Ensure target is within base directory
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError(
            f"Invalid output path: '{user_path}'. Path must be within the application directory."
        )

    return str(target)


def validate_file_size(file_obj, max_mb: int = 50) -> bool:
    """Check if uploaded file exceeds size limit."""
    if hasattr(file_obj, "size") and file_obj.size > max_mb * 1024 * 1024:
        return False
    return True


# -------------------------------------------------------------------------
# QR CODE MATCHING ENGINE
# -------------------------------------------------------------------------
def build_qr_cache(uploaded_files: List) -> Dict[str, bytes]:
    """
    Build a lookup cache for QR code images from uploaded files.
    Stores image bytes to avoid holding file handles.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects

    Returns:
        Dictionary mapping normalized filenames to image bytes
    """
    cache: Dict[str, bytes] = {}

    for fp in uploaded_files:
        if not validate_file_size(fp):
            st.warning(f"File {fp.name} exceeds size limit and was skipped.")
            continue

        # Store multiple key variants for flexible matching
        name_lower = str(fp.name).strip().lower()
        base_name = os.path.splitext(name_lower)[0]

        # Read bytes immediately
        fp.seek(0)
        img_bytes = fp.read()

        cache[name_lower] = img_bytes
        cache[base_name] = img_bytes

        # Strip Windows duplicate indicators: "file (1).png" -> "file"
        stripped = re.sub(r"\s*\(\d+\)", "", base_name).strip()
        if stripped != base_name:
            cache[stripped] = img_bytes

    return cache


def find_qr_image(qr_filename: str, cache: Dict[str, bytes]) -> Optional[bytes]:
    """
    Find QR image bytes by filename with fuzzy matching.

    Args:
        qr_filename: Expected QR filename from Excel
        cache: QR image cache dictionary

    Returns:
        Image bytes if found, None otherwise
    """
    if not qr_filename or str(qr_filename).lower() == "nan":
        return None

    lookup = str(qr_filename).strip().lower()
    base_lookup = os.path.splitext(lookup)[0]

    # Try multiple lookup strategies
    candidates = [
        lookup,
        base_lookup,
        lookup + ".png",
        lookup + ".jpg",
        lookup + ".jpeg",
        base_lookup + ".png",
        base_lookup + ".jpg",
        base_lookup + ".jpeg",
    ]

    for candidate in candidates:
        if candidate in cache:
            return cache[candidate]

    return None


# -------------------------------------------------------------------------
# PDF GENERATION
# -------------------------------------------------------------------------
def add_label_to_pdf(
    pdf_canvas: canvas.Canvas,
    label_img: Image.Image,
    page_size: Tuple[float, float] = letter
) -> None:
    """
    Add a label image to a PDF page, centered and scaled to fit.

    Args:
        pdf_canvas: ReportLab canvas instance
        label_img: Label PIL Image
        page_size: Page dimensions as (width, height) in points
    """
    page_w, page_h = page_size

    # Calculate scale to fit within margins
    max_w = page_w - (PDF_MARGIN_PTS * 2)
    max_h = page_h - (PDF_MARGIN_PTS * 2)

    scale = min(max_w / label_img.width, max_h / label_img.height)
    draw_w = label_img.width * scale
    draw_h = label_img.height * scale

    x_offset = (page_w - draw_w) / 2
    y_offset = (page_h - draw_h) / 2

    # Convert to bytes for ImageReader
    img_buffer = io.BytesIO()
    label_img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    pdf_img = ImageReader(img_buffer)
    pdf_canvas.drawImage(pdf_img, x_offset, y_offset, width=draw_w, height=draw_h)
    pdf_canvas.showPage()


# -------------------------------------------------------------------------
# BATCH PROCESSING ENGINE
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
    """
    Process all valid rows and generate ZIP + PDF outputs.

    Args:
        df: Parsed DataFrame
        schema: Column mapping
        logo_img: Logo PIL Image
        qr_cache: QR image cache
        output_dir: Local output directory
        label_width: Label width in pixels
        label_height: Label height in pixels
        font_size: Base font size
        progress_bar: Streamlit progress bar object
        status_text: Streamlit empty container for status

    Returns:
        Tuple of (count, zip_bytes, pdf_bytes)
    """
    os.makedirs(output_dir, exist_ok=True)

    hdr_comp = schema["company"]
    hdr_prod = schema["product"]
    hdr_client = schema["client"]
    hdr_std = schema["standard"]
    hdr_qr = schema["qr"]

    # Filter valid rows
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

            # Skip invalid rows
            if not qr_name or qr_name.lower() == "nan" or company.lower() == "nan":
                progress_bar.progress((idx + 1) / total)
                continue

            status_text.markdown(
                f"⚙️ *Processing:* **{processed + 1}** — `{company[:50]}...`"
            )

            # Find QR image
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

            # Generate label
            try:
                label = render_compliance_label(
                    qr_img, logo_img, company, product, standard, client,
                    label_width, label_height, font_size
                )
            except Exception as e:
                st.error(f"Failed to render label for '{company}': {e}")
                progress_bar.progress((idx + 1) / total)
                continue

            # Save to disk
            safe_id = re.sub(r"[^\w\-]", "_", client if client and client.lower() != "nan" else f"row_{idx}")
            filename = f"Label_{safe_id}.jpg"
            filepath = os.path.join(output_dir, filename)

            try:
                label.save(filepath, "JPEG", quality=95)
            except Exception as e:
                st.warning(f"Failed to save {filename}: {e}")

            # Add to ZIP
            img_buffer = io.BytesIO()
            label.save(img_buffer, format="JPEG", quality=95)
            zf.writestr(filename, img_buffer.getvalue())

            # Add to PDF
            add_label_to_pdf(pdf, label)

            processed += 1
            progress_bar.progress((idx + 1) / total)

    pdf.save()

    zip_buffer.seek(0)
    pdf_buffer.seek(0)

    return processed, zip_buffer.getvalue(), pdf_buffer.getvalue()


# -------------------------------------------------------------------------
# INTERFACE CONTROL DECK
# -------------------------------------------------------------------------
st.markdown(f"""
    <div class="main-title-container">
        <div class="title-line-primary">{APP_TITLE}</div>
        <div class="title-line-secondary">{APP_SUBTITLE}</div>
    </div>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="sub-title">High-Level Official Verification Console & '
    'Multi-Field Graphic Assembly Line</div>',
    unsafe_allow_html=True
)

# Sidebar controls
st.sidebar.markdown("### 🎛️ Geometric Canvas Controllers")
ui_width = st.sidebar.slider("Label Width (px)", 800, 2400, 1200, step=100)
ui_height = st.sidebar.slider("Label Height (px)", 500, 1500, 680, step=20)
ui_font_sz = st.sidebar.slider("Base Font Size", 16, 60, 32, step=2)

st.sidebar.markdown("---")
ui_disk_path = st.sidebar.text_input(
    "Output Directory",
    value=DEFAULT_OUTPUT_DIR,
    help="Relative path within the application directory. Path traversal is blocked for security."
)

# Initialize session state
for key, default in {
    "zip_bytes": None,
    "pdf_bytes": None,
    "process_ok": False,
    "compiled_count": 0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Tabs
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
        input_excel = st.file_uploader(
            "1. Excel Registry File",
            type=["xlsx", "xls"],
            help="Must contain columns: Company Name, QR Filename (fuzzy matching supported)"
        )
    with c2:
        input_logo = st.file_uploader(
            "2. Standard Mark",
            type=["png", "jpg", "jpeg"],
            help="National standards mark or certification logo"
        )

    input_bulk_qrs = st.file_uploader(
        "3. QR Code Images (batch upload)",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        help="Upload all QR images referenced in the Excel file"
    )

    if st.button("Execute Batch Pipeline", type="primary"):
        # Validate inputs
        if not input_excel or not input_logo or not input_bulk_qrs:
            st.error("Please provide all required inputs: Excel file, logo, and QR code images.")
        else:
            try:
                # Sanitize output path
                safe_output_dir = sanitize_output_path(ui_disk_path)

                # Parse Excel
                df, schema = parse_excel_workbook(input_excel)
                st.info(f"Parsed {len(df)} rows. Detected headers: {list(schema.values())}")

                # Load logo
                logo_img = Image.open(input_logo)

                # Build QR cache
                qr_cache = build_qr_cache(input_bulk_qrs)
                st.info(f"Loaded {len(qr_cache)} unique QR image variants into cache.")

                # Process batch
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

    # Download section
    if st.session_state.process_ok and st.session_state.zip_bytes:
        st.markdown(f"""
            <div class="success-panel">
                <h4 style="color: #15A34A; margin-top: 0;">
                    ✅ Batch Generation Complete
                </h4>
                <p style="color: #1F2937; margin-bottom: 0;">
                    Processed <b>{st.session_state.compiled_count}</b> compliance labels.
                </p>
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