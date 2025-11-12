import json
from datetime import datetime
import fitz  # PyMuPDF
from pathlib import Path

# ---------------- Font helpers ----------------
_FONT_CACHE: dict[str, fitz.Font] = {}

def load_font(fontfile: str) -> fitz.Font:
    """Load and cache an external TTF/OTF font for PyMuPDF."""
    p = str(Path(fontfile).expanduser())
    if p not in _FONT_CACHE:
        _FONT_CACHE[p] = fitz.Font(fontfile=p)  # raises if path invalid
    return _FONT_CACHE[p]

def resolve_font(item: dict, default_fontfile: str | None) -> str | fitz.Font:
    """
    Returns a font argument for PyMuPDF:
      - fitz.Font object if an external 'fontfile' is available (field or global)
      - a built-in font name string otherwise (e.g., 'helv' / 'helv-bold')
    """
    fontfile = item.get("fontfile") or default_fontfile
    if fontfile:
        try:
            return load_font(fontfile)
        except Exception as e:
            raise RuntimeError(f"Failed to load font '{fontfile}': {e}")
    # fallback to built-ins (ASCII only!)
    font = item.get("font", "helv")
    if item.get("bold") and font == "helv":
        return "helv-bold"
    return font

# ---------------- Drawing primitives ----------------
def draw_text(page, text, rect=None, x=None, y=None,
              fontname="helv", size=11, align="left",
              wrap=False, leading=1.2):
    if rect is not None:
        r = fitz.Rect(*rect)
        if wrap:
            page.insert_textbox(
                r, text or "",
                fontname=fontname, fontsize=size,
                align={"left": 0, "center": 1, "right": 2}.get(align, 0),
                lineheight=size * leading,
            )
        else:
            baseline = r.y0 + (r.height / 2) + (size * 0.35)
            page.insert_text((r.x0, baseline), text or "",
                             fontname=fontname, fontsize=size)
    else:
        if x is None or y is None:
            raise ValueError("Provide either rect or (x, y) for text placement.")
        page.insert_text((x, y), text or "", fontname=fontname, fontsize=size)

def draw_checkbox(page, checked, x, y, size=12, style="check", fontname="helv"):
    mark = "✓" if style == "check" else "■"
    if checked:
        page.insert_text((x, y), mark, fontname=fontname, fontsize=size)

def draw_radio(page, choice_value, options, size=12, fontname="helv"):
    # options: [{"value":"male","x":100,"y":220}, ...]
    for opt in options:
        if str(opt["value"]) == str(choice_value):
            page.insert_text((opt["x"], opt["y"]), "●", fontname=fontname, fontsize=size)

def draw_grid_text(page, text, start_x, start_y, cell_w, cell_h,
                   count=None, size=11, upper=False, spacing_adjust=0, fontname="helv"):
    s = "" if text is None else str(text)
    if upper:
        s = s.upper()
    if count is not None:
        s = s[:count]
    x = start_x
    y = start_y
    for ch in s:
        page.insert_text((x + cell_w*0.28 + spacing_adjust, y + cell_h*0.75),
                         ch, fontname=fontname, fontsize=size)
        x += cell_w

def to_date(value, fmt_in=None, fmt_out="%Y-%m-%d"):
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):  # unix ts
        return datetime.utcfromtimestamp(value).strftime(fmt_out)
    s = str(value)
    if fmt_in:
        return datetime.strptime(s, fmt_in).strftime(fmt_out)
    for cand in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, cand).strftime(fmt_out)
        except Exception:
            pass
    return s

# ---------------- Main fill ----------------
def fill_pdf(template_pdf, answers_json, layout_json, out_pdf):
    with open(answers_json, "r", encoding="utf-8") as f:
        answers = json.load(f)
    with open(layout_json, "r", encoding="utf-8") as f:
        layout = json.load(f)

    default_fontfile = layout.get("default_fontfile")  # optional global JP font

    doc = fitz.open(template_pdf)
    num_pages = len(doc)

    for item in layout.get("fields", []):
        page_idx = int(item.get("page", 0))
        if not (0 <= page_idx < num_pages):
            continue
        page = doc[page_idx]

        # Resolve font for this field
        font_arg = resolve_font(item, default_fontfile)

        key = item["key"]
        ftype = item.get("type", "text")
        size = item.get("size", 11)
        align = item.get("align", "left")
        leading = item.get("leading", 1.2)

        # dotted-key lookup
        value = answers
        for part in key.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break

        if ftype in ("text", "textbox", "date"):
            rect = item.get("rect")
            x = item.get("x")
            y = item.get("y")

            if ftype == "date":
                text = to_date(value, fmt_in=item.get("fmt_in"), fmt_out=item.get("fmt_out", "%Y-%m-%d"))
                draw_text(page, text, rect=rect, x=x, y=y,
                          fontname=font_arg, size=size, align=align,
                          wrap=False, leading=leading)
            else:
                text = "" if value is None else str(value)
                wrap = (ftype == "textbox") or bool(item.get("wrap", False))
                if ftype == "textbox" and rect is None:
                    raise ValueError(f"{key}: textbox requires 'rect'")
                draw_text(page, text, rect=rect, x=x, y=y,
                          fontname=font_arg, size=size, align=align,
                          wrap=wrap, leading=leading)

        elif ftype == "checkbox":
            checked = str(value).lower() in ("1", "true", "yes", "y", "on")
            draw_checkbox(page, checked, item["x"], item["y"],
                          size=item.get("mark_size", size),
                          style=item.get("style", "check"),
                          fontname=font_arg)

        elif ftype == "radio":
            draw_radio(page, value, item["options"],
                       size=item.get("mark_size", size),
                       fontname=font_arg)

        elif ftype == "grid":
            draw_grid_text(
                page,
                value,
                start_x=item["x"],
                start_y=item["y"],
                cell_w=item["cell_w"],
                cell_h=item.get("cell_h", item["cell_w"]),
                count=item.get("count"),
                size=size,
                upper=bool(item.get("upper", False)),
                spacing_adjust=item.get("spacing_adjust", 0),
                fontname=font_arg,
            )
        else:
            # unsupported types silently ignored
            pass

    doc.save(out_pdf, deflate=True, garbage=4)
    doc.close()

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Fill a non-fillable questionnaire PDF using JSON + layout.")
    p.add_argument("--template", required=True)
    p.add_argument("--answers", required=True)
    p.add_argument("--layout", required=True)
    p.add_argument("--out", default="filled_questionnaire.pdf")
    args = p.parse_args()
    fill_pdf(args.template, args.answers, args.layout, args.out)
