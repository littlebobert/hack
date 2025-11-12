import json
import base64
import sys
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
from pdf2image import convert_from_path

# === 設定 ===
load_dotenv()
client = OpenAI()

FORM_PATH = Path("questionnaire.pdf")
ANSWERS_PATH = Path("answers.json")
FIELDS_CACHE_PATH = Path("fields_cache_pdf.json")
OUTPUT_PATH = Path("filled_form.pdf")
DEBUG_OUTPUT_PATH = Path("filled_form_debug.pdf")

# コマンドライン引数チェック
FORCE_REFRESH = "--refresh" in sys.argv or "-r" in sys.argv
DEBUG_MODE = "--debug" in sys.argv or "-d" in sys.argv

# === 使い方表示 ===
if "--help" in sys.argv or "-h" in sys.argv:
    print("""
使い方:
  python gen_pdf.py           # キャッシュがあればそれを使用
  python gen_pdf.py --refresh # Vision APIで座標を再取得（お金がかかります）
  python gen_pdf.py -r        # --refreshの短縮形
  python gen_pdf.py --debug   # デバッグモード（座標マーカーを表示）
  python gen_pdf.py -d        # --debugの短縮形
  python gen_pdf.py --help    # このヘルプを表示

ファイル:
  - questionnaire.pdf         : 入力PDFフォーム
  - answers.json              : 埋め込む回答データ
  - fields_cache_pdf.json     : Vision APIで取得した座標（手動編集可能）
  - filled_form.pdf           : 出力PDF
  - filled_form_debug.pdf     : デバッグ版PDF（座標マーカー付き）
    """)
    sys.exit(0)

print("🔍 Checking if PDF has fillable form fields...")

# === 1️⃣ PDFがフォームフィールドを持っているか確認 ===
reader = PdfReader(FORM_PATH)
has_form_fields = False
if "/AcroForm" in reader.trailer["/Root"]:
    has_form_fields = True
    print("✓ PDF has fillable form fields (AcroForm)")
else:
    print("ℹ️  PDF does not have fillable form fields. Will use overlay method.")

# === 2️⃣ Vision APIでフィールド位置を解析 ===
if FIELDS_CACHE_PATH.exists() and not FORCE_REFRESH:
    print("📂 Loading cached field positions from fields_cache_pdf.json")
    print("   (座標を再取得する場合: python gen_pdf.py --refresh)")
    fields = json.loads(FIELDS_CACHE_PATH.read_text())
else:
    if FORCE_REFRESH:
        print("🔄 Force refreshing field positions...")
    print("🔍 Analyzing PDF with Vision API (this costs money)...")
    
    # PDFを高解像度画像に変換（精度向上のため300dpi）
    DPI = 300
    print(f"   Converting PDF to image at {DPI} DPI...")
    images = convert_from_path(FORM_PATH, first_page=1, last_page=1, dpi=DPI)
    
    # 画像をbase64エンコード
    img_buffer = io.BytesIO()
    images[0].save(img_buffer, format='PNG')
    image_data = base64.b64encode(img_buffer.getvalue()).decode()
    
    # PDF情報を取得
    pdf_width = float(reader.pages[0].mediabox.width)
    pdf_height = float(reader.pages[0].mediabox.height)
    img_width, img_height = images[0].size
    
    # 座標変換の倍率を計算
    scale_x = pdf_width / img_width
    scale_y = pdf_height / img_height
    
    print(f"   PDF size: {pdf_width:.1f} x {pdf_height:.1f} points")
    print(f"   Image size: {img_width} x {img_height} pixels")
    print(f"   Scale: x={scale_x:.4f}, y={scale_y:.4f}")
    
    vision_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": (
                         f"Analyze this Japanese clinic questionnaire form.\n\n"
                         f"**Image Information:**\n"
                         f"- Image size: {img_width}x{img_height} pixels\n"
                         f"- PDF size: {pdf_width:.1f}x{pdf_height:.1f} points\n"
                         f"- Coordinate conversion: pdf_x = image_x * {scale_x:.4f}, pdf_y = {pdf_height:.1f} - (image_y * {scale_y:.4f})\n\n"
                         f"**Task:**\n"
                         f"Identify ALL input fields and checkboxes. Look for these Japanese labels:\n"
                         f"- お名前 (Name)\n"
                         f"- 生年月日 (Date of Birth)\n"
                         f"- 性別 (Gender) - CHECKBOX: □男性 □女性 □その他\n"
                         f"- 電話番号 (Phone)\n"
                         f"- 住所 (Address)\n"
                         f"- 来院の目的 / 主な症状 (Reason for visit)\n"
                         f"- 現在治療中の病気 (Ongoing conditions)\n"
                         f"- 現在服用している薬 (Current medication)\n"
                         f"- 薬・食べ物のアレルギー (Allergies)\n"
                         f"- 喫煙 (Smoking) - CHECKBOX: □吸う □吸わない\n"
                         f"- 飲酒 (Alcohol) - CHECKBOX: □飲む □飲まない\n"
                         f"- 睡眠時間 (Sleep hours)\n"
                         f"- 署名 (Signature)\n"
                         f"- 日付 (Date)\n\n"
                         f"**Instructions:**\n"
                         f"1. For TEXT fields: Provide the EXACT pixel coordinates (in the image) where text should START\n"
                         f"2. For CHECKBOX fields: Provide pixel coordinates for the CENTER of each checkbox\n"
                         f"3. Measure coordinates carefully from the image\n"
                         f"4. Font size should be 10-12 points\n"
                         f"5. Return coordinates in IMAGE space (I will convert to PDF space)\n\n"
                         f"**Return JSON format:**\n"
                         f'{{\n'
                         f'  "fields": [\n'
                         f'    {{"field":"name", "type":"text", "image_x":500, "image_y":300, "font_size":12}},\n'
                         f'    {{"field":"gender", "type":"checkbox", "options":[\n'
                         f'      {{"label":"male", "image_x":550, "image_y":420}},\n'
                         f'      {{"label":"female", "image_x":650, "image_y":420}},\n'
                         f'      {{"label":"other", "image_x":750, "image_y":420}}\n'
                         f'    ]}}\n'
                         f'  ]\n'
                         f'}}\n\n'
                         f"Return ONLY the JSON, no other text."
                     )},
                    {"type": "image_url",
                     "image_url": {
                         "url": f"data:image/png;base64,{image_data}"
                     }},
                ],
            }
        ],
    )
    
    fields_json = vision_response.choices[0].message.content.strip()
    
    # マークダウンのコードブロックを除去
    if fields_json.startswith("```"):
        lines = fields_json.split("\n")
        fields_json = "\n".join(lines[1:-1])
    
    try:
        response_data = json.loads(fields_json)
        fields_raw = response_data.get("fields", response_data) if isinstance(response_data, dict) else response_data
    except Exception as e:
        print("⚠️ Could not parse model output as JSON. Raw output:\n", fields_json)
        raise e
    
    # 画像座標からPDF座標に変換
    print("   Converting image coordinates to PDF coordinates...")
    fields = []
    for f in fields_raw:
        converted_field = {
            "field": f["field"],
            "type": f["type"]
        }
        
        if f["type"] == "text":
            # テキストフィールド: 画像座標 → PDF座標に変換
            image_x = f.get("image_x", f.get("x", 0))
            image_y = f.get("image_y", f.get("y", 0))
            
            pdf_x = image_x * scale_x
            pdf_y = pdf_height - (image_y * scale_y)
            
            converted_field["x"] = round(pdf_x, 1)
            converted_field["y"] = round(pdf_y, 1)
            converted_field["font_size"] = f.get("font_size", 12)
            
        elif f["type"] == "checkbox" and "options" in f:
            # チェックボックス: 各オプションの座標を変換
            converted_options = []
            for opt in f["options"]:
                image_x = opt.get("image_x", opt.get("x", 0))
                image_y = opt.get("image_y", opt.get("y", 0))
                
                pdf_x = image_x * scale_x
                pdf_y = pdf_height - (image_y * scale_y)
                
                converted_options.append({
                    "label": opt["label"],
                    "x": round(pdf_x, 1),
                    "y": round(pdf_y, 1)
                })
            converted_field["options"] = converted_options
        
        fields.append(converted_field)
    
    # キャッシュに保存
    FIELDS_CACHE_PATH.write_text(json.dumps(fields, indent=2, ensure_ascii=False))
    print(f"💾 Saved field positions to {FIELDS_CACHE_PATH}")

print("Detected fields:")
print(json.dumps(fields, indent=2, ensure_ascii=False))

# === 3️⃣ 回答データをロード ===
answers = json.loads(ANSWERS_PATH.read_text())

# === 4️⃣ PDFに書き込み ===
print("\n✍️  Writing to PDF...")

# 日本語フォントを登録
font_name = 'Helvetica'
try:
    # macOSの日本語フォント（TrueTypeのみサポート）
    hiragino_path = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
    if Path(hiragino_path).exists():
        # TTCファイルの場合、最初のフォントを使用
        pdfmetrics.registerFont(TTFont('Japanese', hiragino_path, subfontIndex=0))
        font_name = 'Japanese'
        print("✓ Using Hiragino font (Japanese support)")
    else:
        print("⚠️  Hiragino font not found, using Helvetica")
except Exception as e:
    print(f"⚠️  Failed to load Japanese font: {e}")
    print("   Using Helvetica (Japanese may not display correctly)")

# オーバーレイPDFを作成
packet = io.BytesIO()
can = canvas.Canvas(packet, pagesize=(
    float(reader.pages[0].mediabox.width),
    float(reader.pages[0].mediabox.height)
))

# フィールド名の柔軟なマッチング
def match_field_name(field_name, answers_dict):
    """フィールド名を柔軟にマッチング"""
    field_lower = field_name.lower()
    
    if field_lower in answers_dict:
        return answers_dict[field_lower]
    
    if field_lower.endswith('s'):
        singular = field_lower[:-1]
        if singular in answers_dict:
            return answers_dict[singular]
    else:
        plural = field_lower + 's'
        if plural in answers_dict:
            return answers_dict[plural]
    
    for key in answers_dict:
        if key in field_lower or field_lower in key:
            return answers_dict[key]
    
    return None

# チェックマーク用のX描画
def draw_checkbox_x(canvas_obj, x, y, size=8):
    """チェックボックスにXマークを描画"""
    canvas_obj.setStrokeColorRGB(0, 0, 0)
    canvas_obj.setLineWidth(2)
    canvas_obj.line(x, y, x + size, y + size)
    canvas_obj.line(x + size, y, x, y + size)

# デバッグマーカー用の関数
def draw_debug_marker(canvas_obj, x, y, color, label=""):
    """座標にデバッグマーカーを描画"""
    # 十字マーク
    size = 10
    canvas_obj.setStrokeColorRGB(*color)
    canvas_obj.setLineWidth(1)
    canvas_obj.line(x - size, y, x + size, y)  # 横線
    canvas_obj.line(x, y - size, x, y + size)  # 縦線
    # 円
    canvas_obj.circle(x, y, 3, stroke=1, fill=0)
    # ラベル
    if label:
        canvas_obj.setFillColorRGB(*color)
        canvas_obj.setFont('Helvetica', 6)
        canvas_obj.drawString(x + 5, y + 5, label)

matched_count = 0

for f in fields:
    field_name = f.get("field", "unknown")
    field_type = f.get("type", "text")
    
    answer_value = match_field_name(field_name, answers)
    
    if field_type == "text":
        x, y = f["x"], f["y"]
        font_size = f.get("font_size", 12)
        
        if answer_value is not None:
            text = str(answer_value)
            
            can.setFont(font_name, font_size)
            can.setFillColorRGB(0, 0, 0)
            can.drawString(x, y, text)
            
            # デバッグモード: 緑のマーカー
            if DEBUG_MODE:
                draw_debug_marker(can, x, y, (0, 0.7, 0), f"{field_name}")
            
            print(f"  ✓ TEXT {field_name}: '{text}' at ({x:.1f}, {y:.1f}), size={font_size}pt")
            matched_count += 1
        else:
            # デバッグモード: 赤いマーカー（値なし）
            if DEBUG_MODE:
                draw_debug_marker(can, x, y, (1, 0, 0), f"{field_name}(no value)")
            print(f"  ✗ TEXT {field_name}: No matching answer found")
    
    elif field_type == "checkbox":
        if answer_value is not None and "options" in f:
            answer_lower = str(answer_value).lower()
            
            checked_any = False
            for option in f["options"]:
                option_label = option.get("label", "").lower()
                option_x, option_y = option["x"], option["y"]
                
                is_match = (
                    answer_lower == option_label or
                    answer_lower in option_label or
                    option_label in answer_lower
                )
                
                if is_match:
                    draw_checkbox_x(can, option_x, option_y, size=10)
                    
                    # デバッグモード: 青いマーカー
                    if DEBUG_MODE:
                        draw_debug_marker(can, option_x, option_y, (0, 0, 1), f"{field_name}={option_label}")
                    
                    print(f"  ✓ CHECKBOX {field_name}: checked '{option_label}' at ({option_x:.1f}, {option_y:.1f})")
                    checked_any = True
                    matched_count += 1
                    break
                elif DEBUG_MODE:
                    # デバッグモード: グレーのマーカー（未選択オプション）
                    draw_debug_marker(can, option_x, option_y, (0.5, 0.5, 0.5), f"{option_label}")
            
            if not checked_any:
                print(f"  ⚠️  CHECKBOX {field_name}: value '{answer_value}' didn't match any option")
        else:
            print(f"  ✗ CHECKBOX {field_name}: No matching answer or missing options")

can.save()

# オーバーレイをマージ
packet.seek(0)
overlay_pdf = PdfReader(packet)
output = PdfWriter()

page = reader.pages[0]
page.merge_page(overlay_pdf.pages[0])
output.add_page(page)

# 残りのページをコピー（複数ページの場合）
for i in range(1, len(reader.pages)):
    output.add_page(reader.pages[i])

# 出力
final_output_path = DEBUG_OUTPUT_PATH if DEBUG_MODE else OUTPUT_PATH
with open(final_output_path, "wb") as output_file:
    output.write(output_file)

print(f"\n✅ Done! Filled {matched_count}/{len(fields)} fields")
print(f"📄 Output saved to {final_output_path}")

if DEBUG_MODE:
    print(f"🔍 Debug mode enabled:")
    print(f"   🟢 Green markers = text fields with values")
    print(f"   🔴 Red markers = text fields without values")
    print(f"   🔵 Blue markers = checked checkboxes")
    print(f"   ⚪ Gray markers = unchecked checkbox options")

