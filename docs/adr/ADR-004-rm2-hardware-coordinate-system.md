# ADR-004: reMarkable 2 Hardware Coordinate System

**Date:** 2026-03-20
**Status:** Accepted — implementation deferred to Phase 2
**Deciders:** User (bdcl)
**Source:** reMarkable Linux kernel source (github.com/reMarkable/linux, branch: zero-sugar)

---

## Context

Phase 2 will render annotation strokes (`.rm` files) as overlays onto the original PDF.
To do this correctly, stroke coordinates from the `.rm` file must be mapped to PDF page
coordinates. This requires understanding the rM2 hardware coordinate system.

---

## Hardware Facts (from kernel source)

### Stylus input — Wacom serial driver
- Driver: `drivers/input/tablet/wacom_serial4.c`
- Input events: `ABS_X`, `ABS_Y`, `ABS_PRESSURE`, `BTN_TOUCH`, `BTN_STYLUS`, `BTN_STYLUS2`
- Stroke data in `.rm` files is derived from these Wacom events

### Display
- Resolution: **1404 × 1872 pixels** (portrait, well-established in community)
- Controller: AU Optronics K190x series epaper
- Framebuffer: `/dev/fb0`
- Color depth: 8-bit grayscale

### Touch input (finger) — FocalTech driver
- Driver: `drivers/input/touchscreen/focaltech_touch/`
- Up to 10 simultaneous touch points
- Separate from stylus — not present in `.rm` annotation files

### Touch coordinate rotation (from official Qt docs)
- `QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS="rotate=180:invertx"`
- The rM2 display is physically rotated 180° with X-axis inverted relative to raw input
- This applies to **finger touch**; Wacom stylus coordinates are handled separately

---

## Coordinate Mapping for Phase 2

When rendering `.rm` strokes onto a PDF page:

```
rM2 device space:   1404 × 1872 px  (portrait)
PDF page space:     variable (points, 72pt = 1 inch)

scale_x = pdf_page_width_pt  / 1404.0
scale_y = pdf_page_height_pt / 1872.0

stroke_x_pt = stroke_x_device * scale_x
stroke_y_pt = stroke_y_device * scale_y
```

PDF coordinate origin is bottom-left; rM2 origin is top-left.
Y-axis must be flipped:

```
stroke_y_pt = pdf_page_height_pt - (stroke_y_device * scale_y)
```

### Landscape documents

If the PDF is landscape-oriented and the user rotated the rM2 to annotate in landscape,
the device coordinate space effectively becomes 1872 × 1404. The `.rm` file's content
transform matrix (stored in `.content` JSON) indicates this rotation. Phase 2 must read
`transform` from `.content` to determine orientation before scaling.

---

## Alternatives Considered

| Approach | Notes |
|----------|-------|
| Fixed 1404×1872 assumption | Works for portrait PDFs, breaks for landscape |
| Read transform from `.content` | Correct — handles portrait and landscape |
| Parse device DPI and use physical units | Overcomplicated; DPI not in `.rm` files |

**Decision:** Read `transform` from the `.content` JSON file, determine orientation,
then apply the appropriate scaling and Y-flip for the PDF target.

---

## USB Networking Note

The rM2 uses **RNDIS gadget mode** for USB networking (not ECM). Relevant per-platform:

| Platform | RNDIS support | Action needed |
|----------|---------------|---------------|
| Linux | Built-in kernel | None |
| Windows 10/11 | Built-in | None |
| macOS | Not included | Install HoRNDIS driver |

This explains why Mac users need HoRNDIS for USB SSH. Documented in README.

---

## Linked Commits

- ADR written: `ffd48bf` (tag: `v0.1.2`)
