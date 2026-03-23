"""Tests for the annotation renderer — no device or .rm files required."""
from __future__ import annotations

import io
import struct
from unittest.mock import MagicMock, patch

import pytest
from reportlab.lib.colors import Color

from rm_bridge.render import (
    RM_HEIGHT_PX,
    RM_WIDTH_PX,
    _COLOR_MAP,
    _ERASER_TOOLS,
    _HIGHLIGHTER_TOOLS,
    _line_width,
    _resolve_color,
    overlay_annotations,
    render_page,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_point(x: float = 100.0, y: float = 200.0, width: int = 10, pressure: int = 100) -> MagicMock:
    pt = MagicMock()
    pt.x = x
    pt.y = y
    pt.width = width
    pt.pressure = pressure
    pt.speed = 50
    pt.direction = 0
    return pt


def _make_line(
    color_name: str = "BLACK",
    tool_name: str = "BALLPOINT_1",
    thickness_scale: float = 1.0,
    num_points: int = 3,
) -> MagicMock:
    line = MagicMock()
    line.color.name = color_name
    line.tool.name = tool_name
    line.thickness_scale = thickness_scale
    line.points = [_make_point(x=float(i * 100), y=float(i * 50)) for i in range(num_points)]
    return line


def _minimal_pdf(width_pt: float = 595.0, height_pt: float = 842.0) -> bytes:
    """Create a minimal valid single-page PDF readable by pypdf."""
    from reportlab.pdfgen import canvas as rl_canvas
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(width_pt, height_pt))
    c.setFont("Helvetica", 1)
    c.drawString(1, 1, " ")   # content required — empty canvas produces 0-page PDF
    c.showPage()
    c.save()
    return buf.getvalue()


# ------------------------------------------------------------------
# Color mapping
# ------------------------------------------------------------------

class TestColorMap:
    def test_all_standard_colors_present(self):
        expected = ["BLACK", "GRAY", "WHITE", "YELLOW", "GREEN", "PINK",
                    "BLUE", "RED", "HIGHLIGHT", "CYAN", "MAGENTA"]
        for color in expected:
            assert color in _COLOR_MAP, f"Missing color: {color}"

    def test_colors_are_valid_rgba(self):
        for name, (r, g, b, a) in _COLOR_MAP.items():
            assert 0.0 <= r <= 1.0, f"{name}: R out of range"
            assert 0.0 <= g <= 1.0, f"{name}: G out of range"
            assert 0.0 <= b <= 1.0, f"{name}: B out of range"
            assert 0.0 <= a <= 1.0, f"{name}: A out of range"

    def test_black_is_opaque(self):
        assert _COLOR_MAP["BLACK"][3] == 1.0

    def test_highlight_is_transparent(self):
        assert _COLOR_MAP["HIGHLIGHT"][3] < 0.5


class TestResolveColor:
    def test_returns_reportlab_color(self):
        color = _resolve_color("BLACK", "BALLPOINT_1")
        assert isinstance(color, Color)

    def test_highlighter_tool_forces_transparency(self):
        color = _resolve_color("BLACK", "HIGHLIGHTER_1")
        assert color.alpha < 0.5

    def test_unknown_color_defaults_to_black(self):
        color = _resolve_color("UNKNOWN_COLOR", "BALLPOINT_1")
        assert color.red == 0.0
        assert color.green == 0.0
        assert color.blue == 0.0

    def test_blue_pen_is_blue(self):
        color = _resolve_color("BLUE", "BALLPOINT_1")
        assert color.blue > color.red


# ------------------------------------------------------------------
# Line width calculation
# ------------------------------------------------------------------

class TestLineWidth:
    def test_returns_positive_value(self):
        line = _make_line(num_points=3)
        w = _line_width(line, scale_x=1.0)
        assert w > 0

    def test_respects_minimum_width(self):
        line = _make_line(num_points=2)
        for pt in line.points:
            pt.width = 0
        line.thickness_scale = 0.0
        w = _line_width(line, scale_x=1.0)
        assert w >= 0.4  # minimum enforced

    def test_respects_maximum_width(self):
        line = _make_line(num_points=2)
        for pt in line.points:
            pt.width = 9999
        line.thickness_scale = 100.0
        w = _line_width(line, scale_x=1.0)
        assert w <= 8.0  # maximum enforced

    def test_empty_points_returns_default(self):
        line = _make_line(num_points=0)
        line.points = []
        w = _line_width(line, scale_x=1.0)
        assert w == 1.0


# ------------------------------------------------------------------
# render_page
# ------------------------------------------------------------------

class TestRenderPage:
    def _mock_tree(self, items):
        tree = MagicMock()
        tree.walk.return_value = iter(items)
        return tree

    def test_returns_pdf_bytes(self):
        with patch("rm_bridge.render.read_tree") as mock_read:
            mock_read.return_value = self._mock_tree([])
            result = render_page(b"fake-rm-data", 595.0, 842.0)
        assert result[:4] == b"%PDF"

    def test_correct_page_dimensions(self):
        from pypdf import PdfReader
        with patch("rm_bridge.render.read_tree") as mock_read:
            mock_read.return_value = self._mock_tree([])
            result = render_page(b"fake-rm-data", 400.0, 600.0)
        reader = PdfReader(io.BytesIO(result))
        page = reader.pages[0]
        assert abs(float(page.mediabox.width) - 400.0) < 1.0
        assert abs(float(page.mediabox.height) - 600.0) < 1.0

    def test_eraser_strokes_skipped(self):
        eraser = _make_line(tool_name="ERASER", num_points=3)
        with patch("rm_bridge.render.read_tree") as mock_read:
            mock_read.return_value = self._mock_tree([eraser])
            # Should complete without error, eraser not drawn
            result = render_page(b"fake-rm-data", 595.0, 842.0)
        assert result[:4] == b"%PDF"

    def test_single_point_stroke_skipped(self):
        line = _make_line(num_points=1)
        with patch("rm_bridge.render.read_tree") as mock_read:
            mock_read.return_value = self._mock_tree([line])
            result = render_page(b"fake-rm-data", 595.0, 842.0)
        assert result[:4] == b"%PDF"

    def test_normal_stroke_rendered(self):
        line = _make_line(color_name="BLUE", tool_name="FINELINER_1", num_points=5)
        with patch("rm_bridge.render.read_tree") as mock_read:
            mock_read.return_value = self._mock_tree([line])
            result = render_page(b"fake-rm-data", 595.0, 842.0)
        assert result[:4] == b"%PDF"

    def test_invalid_rm_raises_value_error(self):
        with pytest.raises(ValueError, match="Failed to parse"):
            render_page(b"not-valid-rm-data", 595.0, 842.0)

    def test_y_axis_flip(self):
        """Strokes at device y=0 (top) should appear at pdf top (high y value)."""
        # We can't easily verify coordinates in the output PDF stream,
        # but we verify no exception and correct output format
        line = _make_line(num_points=2)
        line.points[0].y = 0.0       # device top
        line.points[1].y = RM_HEIGHT_PX  # device bottom
        with patch("rm_bridge.render.read_tree") as mock_read:
            mock_read.return_value = self._mock_tree([line])
            result = render_page(b"fake", 595.0, 842.0)
        assert result[:4] == b"%PDF"


# ------------------------------------------------------------------
# overlay_annotations
# ------------------------------------------------------------------

class TestOverlayAnnotations:
    def test_no_annotations_returns_original(self):
        original = _minimal_pdf()
        result = overlay_annotations(original, {})
        # Should be a valid PDF
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(result))
        assert len(reader.pages) == 1

    def test_preserves_page_count(self):
        from pypdf import PdfReader
        from reportlab.pdfgen import canvas as rl_canvas
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(595, 842))
        c.setFont("Helvetica", 1)
        c.drawString(1, 1, " ")
        c.showPage()
        c.drawString(1, 1, " ")
        c.showPage()
        c.save()
        original = buf.getvalue()

        result = overlay_annotations(original, {})
        reader = PdfReader(io.BytesIO(result))
        assert len(reader.pages) == 2

    def test_annotation_applied_with_page_order(self):
        original = _minimal_pdf()
        page_uuid = "aaaa-bbbb-cccc"

        fake_line = _make_line(num_points=3)
        with patch("rm_bridge.render.read_tree") as mock_read:
            tree = MagicMock()
            tree.walk.return_value = iter([fake_line])
            mock_read.return_value = tree
            result = overlay_annotations(
                original,
                {page_uuid: b"fake-rm"},
                page_order=[page_uuid],
            )
        from pypdf import PdfReader
        assert PdfReader(io.BytesIO(result)).pages[0] is not None

    def test_annotation_applied_with_integer_keys(self):
        original = _minimal_pdf()

        fake_line = _make_line(num_points=3)
        with patch("rm_bridge.render.read_tree") as mock_read:
            tree = MagicMock()
            tree.walk.return_value = iter([fake_line])
            mock_read.return_value = tree
            result = overlay_annotations(original, {"0": b"fake-rm"})
        from pypdf import PdfReader
        assert PdfReader(io.BytesIO(result)).pages[0] is not None

    def test_bad_annotation_skipped_gracefully(self):
        """A corrupt .rm file on one page should not abort the whole document."""
        original = _minimal_pdf()
        with patch("rm_bridge.render.read_tree", side_effect=Exception("corrupt")):
            result = overlay_annotations(original, {"0": b"garbage"})
        from pypdf import PdfReader
        # Document still produced, page still present
        assert len(PdfReader(io.BytesIO(result)).pages) == 1

    def test_out_of_range_page_order_ignored(self):
        original = _minimal_pdf()
        # page_order has 3 entries but PDF only has 1 page — should not crash
        result = overlay_annotations(original, {}, page_order=["a", "b", "c"])
        from pypdf import PdfReader
        assert len(PdfReader(io.BytesIO(result)).pages) == 1
