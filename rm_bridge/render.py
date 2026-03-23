"""Annotation renderer — .rm strokes → overlay on original PDF.

Pipeline:
    pull_annotations() → {page_uuid: rm_bytes}
    render_page(rm_bytes, width_pt, height_pt) → annotation PDF bytes
    overlay_annotations(original_pdf, annotations, page_order) → merged PDF bytes

Coordinate mapping (ADR-004):
    rM2 device space: 1404 × 1872 px at 226 DPI
    scale_x = page_width_pt  / 1404
    scale_y = page_height_pt / 1872
    y_pt = page_height_pt - (y_device * scale_y)   # Y-axis flip (device=top-left, PDF=bottom-left)
"""
from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas
from rmscene import UnreadableBlock, read_tree
from rmscene.scene_items import Line

# ------------------------------------------------------------------
# Device constants (reMarkable 2)
# ------------------------------------------------------------------

RM_WIDTH_PX: int = 1404
RM_HEIGHT_PX: int = 1872

# ------------------------------------------------------------------
# Color map  PenColor.name → (R, G, B, alpha)
# ------------------------------------------------------------------

_COLOR_MAP: dict[str, tuple[float, float, float, float]] = {
    "BLACK":        (0.00, 0.00, 0.00, 1.00),
    "GRAY":         (0.50, 0.50, 0.50, 1.00),
    "WHITE":        (1.00, 1.00, 1.00, 1.00),
    "YELLOW":       (1.00, 0.90, 0.00, 0.35),
    "GREEN":        (0.00, 0.78, 0.20, 1.00),
    "PINK":         (1.00, 0.45, 0.65, 1.00),
    "BLUE":         (0.18, 0.40, 0.95, 1.00),
    "RED":          (0.88, 0.10, 0.10, 1.00),
    "GRAY_OVERLAP": (0.50, 0.50, 0.50, 0.50),
    "HIGHLIGHT":    (1.00, 0.90, 0.00, 0.30),
    "GREEN_2":      (0.00, 0.70, 0.35, 1.00),
    "CYAN":         (0.00, 0.80, 0.90, 1.00),
    "MAGENTA":      (0.80, 0.00, 0.80, 1.00),
    "YELLOW_2":     (0.90, 0.90, 0.00, 1.00),
}

_ERASER_TOOLS: frozenset[str] = frozenset({"ERASER", "ERASER_AREA"})

# Tools that render as semi-transparent highlight strokes
_HIGHLIGHTER_TOOLS: frozenset[str] = frozenset({"HIGHLIGHTER_1", "HIGHLIGHTER_2"})


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _resolve_color(color_name: str, tool_name: str) -> Color:
    r, g, b, a = _COLOR_MAP.get(color_name, (0.0, 0.0, 0.0, 1.0))
    if tool_name in _HIGHLIGHTER_TOOLS:
        a = 0.30
    return Color(r, g, b, alpha=a)


def _line_width(line: Line, scale_x: float) -> float:
    """Convert device stroke width to PDF points."""
    if not line.points:
        return 1.0
    avg_device_width = sum(p.width for p in line.points) / len(line.points)
    raw = avg_device_width * line.thickness_scale * scale_x
    # Clamp to a readable range — very thin strokes still need to be visible
    return max(0.4, min(raw * 0.28, 8.0))


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def render_page(
    rm_bytes: bytes,
    page_width_pt: float,
    page_height_pt: float,
) -> bytes:
    """Render .rm annotation bytes onto a transparent PDF page.

    Returns PDF bytes (single page, same dimensions as target PDF page).
    Eraser strokes are skipped. Unreadable blocks are skipped with a warning.

    Args:
        rm_bytes: Raw bytes of one .rm annotation file.
        page_width_pt: Target PDF page width in points.
        page_height_pt: Target PDF page height in points.
    """
    scale_x = page_width_pt / RM_WIDTH_PX
    scale_y = page_height_pt / RM_HEIGHT_PX

    try:
        tree = read_tree(io.BytesIO(rm_bytes))
    except Exception as e:
        raise ValueError(f"Failed to parse .rm file: {e}") from e

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width_pt, page_height_pt))
    c.setLineCap(1)   # round caps
    c.setLineJoin(1)  # round joins

    for item in tree.walk():
        if isinstance(item, UnreadableBlock):
            print(f"[warn] skipping unreadable block in .rm file")
            continue

        if not isinstance(item, Line):
            continue

        tool_name = item.tool.name
        if tool_name in _ERASER_TOOLS:
            continue

        if len(item.points) < 2:
            continue

        color = _resolve_color(item.color.name, tool_name)
        width_pt = _line_width(item, scale_x)

        c.saveState()
        c.setStrokeColor(color)
        c.setLineWidth(width_pt)

        path = c.beginPath()
        first = item.points[0]
        path.moveTo(
            first.x * scale_x,
            page_height_pt - (first.y * scale_y),  # flip Y
        )
        for pt in item.points[1:]:
            path.lineTo(
                pt.x * scale_x,
                page_height_pt - (pt.y * scale_y),
            )
        c.drawPath(path, stroke=1, fill=0)
        c.restoreState()

    c.save()
    return buf.getvalue()


def overlay_annotations(
    original_pdf_bytes: bytes,
    annotations: dict[str, bytes],
    page_order: list[str] | None = None,
) -> bytes:
    """Merge annotation layers onto the original PDF.

    Args:
        original_pdf_bytes: Original PDF file bytes.
        annotations: Mapping of page key → raw .rm bytes.
                     Keys are page UUIDs (from pull_annotations).
        page_order: Optional list of page UUIDs in PDF page order,
                    as returned by DocumentContent.pages.
                    If None, keys are treated as integer page indices ("0", "1", …).

    Returns:
        PDF bytes with annotations composited onto each matching page.
    """
    reader = PdfReader(io.BytesIO(original_pdf_bytes))
    writer = PdfWriter()

    for page_idx, page in enumerate(reader.pages):
        # Resolve which annotation key corresponds to this page index
        if page_order is not None:
            key = page_order[page_idx] if page_idx < len(page_order) else None
        else:
            key = str(page_idx)

        if key and key in annotations:
            width_pt = float(page.mediabox.width)
            height_pt = float(page.mediabox.height)

            try:
                annotation_pdf = render_page(annotations[key], width_pt, height_pt)
                annotation_page = PdfReader(io.BytesIO(annotation_pdf)).pages[0]
                page.merge_page(annotation_page)
            except Exception as e:
                print(f"[warn] failed to render annotation for page {page_idx}: {e}")

        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
