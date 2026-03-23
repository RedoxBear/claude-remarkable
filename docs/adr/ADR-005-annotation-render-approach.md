# ADR-005: Annotation Render Approach — reportlab + pypdf over SVG intermediary

**Date:** 2026-03-20
**Status:** Accepted
**Deciders:** User (bdcl)

---

## Context

Phase 2 requires rendering `.rm` annotation stroke files as overlays on the original PDF.
The pipeline is:

```
.rm bytes → rmscene parse → stroke data → draw onto PDF page → merge with original
```

Several rendering approaches exist in the community.

---

## Decision

**Direct PDF rendering: reportlab canvas → pypdf merge_page**

No SVG or image intermediary. Strokes are drawn directly onto a reportlab `Canvas`,
saved as a single-page PDF, then composited onto the original using `pypdf.merge_page()`.

### Pipeline

```
render_page(rm_bytes, width_pt, height_pt) → annotation PDF bytes
overlay_annotations(original_pdf, {page_uuid: rm_bytes}, page_order) → merged PDF bytes
```

### Coordinate mapping (from ADR-004)

```
scale_x = page_width_pt  / 1404   (rM2 device width in px)
scale_y = page_height_pt / 1872   (rM2 device height in px)

x_pt = stroke_x * scale_x
y_pt = page_height_pt - (stroke_y * scale_y)   # Y-axis flip
```

### Stroke width

```
avg_device_width = mean(point.width for point in stroke.points)
width_pt = clamp(avg_device_width * thickness_scale * scale_x * 0.28, 0.4, 8.0)
```

Average per-point width is used rather than varying width per segment — this avoids
drawing many short path segments and keeps the output compact.

### Color and transparency

Colors are mapped from `PenColor` enum names to RGBA tuples. Highlighter tools
(`HIGHLIGHTER_1`, `HIGHLIGHTER_2`) override alpha to 0.30 regardless of color.
Eraser tools (`ERASER`, `ERASER_AREA`) are skipped entirely — not rendered.

### Page order

Annotation files are keyed by page UUID (matching `DocumentContent.pages`).
`overlay_annotations` accepts an optional `page_order: list[str]` to map
page index → UUID correctly. Without it, falls back to integer string keys
("0", "1", …) for simple cases.

---

## Alternatives Rejected

| Option | Why Rejected |
|--------|-------------|
| SVG intermediary (via rmc/Inkscape) | Requires Inkscape binary on host — unacceptable dependency |
| PNG rasterisation per page | Loses PDF vector quality; large file sizes |
| Per-point varying width (segment-by-segment) | High path complexity, large PDFs, marginal quality gain |
| Separate annotation PDF file | User expects a single merged file output |

---

## Known Limitations

- **Varying stroke width per point** is not implemented — average width is used.
  This is a quality trade-off, not a correctness issue.
- **Text annotations** (typed text in reMarkable) are not rendered in Phase 2.
  rmscene exposes `Text` items; rendering them requires font handling — deferred.
- **PDF highlight annotations** (GlyphRange) are not rendered — deferred.
- **Landscape PDFs**: `merge_page` composites at the PDF coordinate level; if the
  original PDF page is landscape, strokes scale correctly because we read
  `page.mediabox.width/height` per-page. No special case needed.
- **pypdf deprecation warning**: `merge_page` on a non-writer-attached page triggers
  a DeprecationWarning in pypdf ≥ 5.x. Will be resolved before v1.0 release by
  cloning pages into the writer before merging.

---

## Linked Commits

- Phase 2 implementation: `2214ba4` (tag: `v0.2.0`)
