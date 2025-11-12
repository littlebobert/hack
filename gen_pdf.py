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

# コマンドライン引数チェック
FORCE_REFRESH = "--refresh" in sys.argv or "-r" in sys.argv

# === 使い方表示 ===
if "--help" in sys.argv or "-h" in sys.argv:
    print("""
使い方:
  python gen_pdf.py           # キャッシュがあればそれを使用
  python gen_pdf.py --refresh # Vision APIで座標を再取得（お金がかかります）
  python gen_pdf.py -r        # --refreshの短縮形
  python gen_pdf.py --help    # このヘルプを表示

ファイル:
  - questionnaire.pdf       : 入力PDFフォーム
  - answers.json            : 埋め込む回答データ
  - fields_cache_pdf.json   : Vision APIで取得した座標
  - filled_form.pdf         : 出力PDF
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
    
    # PDFを画像に変換（1ページ目のみ）
    images = convert_from_path(FORM_PATH, first_page=1, last_page=1, dpi=150)
    
    # 画像をbase64エンコード
    img_buffer = io.BytesIO()
    images[0].save(img_buffer, format='PNG')
    image_data = base64.b64encode(img_buffer.getvalue()).decode()
    
    pdf_width = float(reader.pages[0].mediabox.width)
    pdf_height = float(reader.pages[0].mediabox.height)
    
    vision_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": (
                         f"Analyze this Japanese PDF questionnaire form (PDF size: {pdf_width}x{pdf_height} points). "
                         f"For each input field, detect:\n"
                         f"1. Field name (e.g., 'name', 'date_of_birth', 'gender', 'phone', 'address')\n"
                         f"2. Field type: 'text' or 'checkbox'\n"
                         f"3. For TEXT fields: x,y coordinates (in PDF points, origin at bottom-left) and font_size\n"
                         f"4. For CHECKBOX fields: list of options with coordinates\n\n"
                         f"IMPORTANT:\n"
                         f"- PDF coordinate system: (0,0) is at BOTTOM-LEFT corner\n"
                         f"- y-coordinate increases UPWARD\n"
                         f"- Convert image coordinates to PDF coordinates: pdf_y = {pdf_height} - image_y\n"
                         f"- '性別 (Gender)' with checkboxes is type 'checkbox'\n"
                         f"- Font size should be 10-14 points for normal fields\n\n"
                         f"Return ONLY valid JSON:\n"
                         f'{{\n'
                         f'  "fields": [\n'
                         f'    {{"field":"name", "type":"text", "x":150, "y":700, "font_size":12}},\n'
                         f'    {{"field":"gender", "type":"checkbox", "options":[\n'
                         f'      {{"label":"male", "x":150, "y":650}},\n'
                         f'      {{"label":"female", "x":200, "y":650}}\n'
                         f'    ]}}\n'
                         f'  ]\n'
                         f'}}\n'
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
        fields = response_data.get("fields", response_data) if isinstance(response_data, dict) else response_data
    except Exception as e:
        print("⚠️ Could not parse model output as JSON. Raw output:\n", fields_json)
        raise e
    
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

matched_count = 0

for f in fields:
    field_name = f.get("field", "unknown")
    field_type = f.get("type", "text")
    
    answer_value = match_field_name(field_name, answers)
    
    if field_type == "text":
        if answer_value is not None:
            text = str(answer_value)
            x, y = f["x"], f["y"]
            font_size = f.get("font_size", 12)
            
            can.setFont(font_name, font_size)
            can.setFillColorRGB(0, 0, 0)
            can.drawString(x, y, text)
            
            print(f"  ✓ TEXT {field_name}: '{text}' at ({x}, {y}), size={font_size}pt")
            matched_count += 1
        else:
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
                    print(f"  ✓ CHECKBOX {field_name}: checked '{option_label}' at ({option_x}, {option_y})")
                    checked_any = True
                    matched_count += 1
                    break
            
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
with open(OUTPUT_PATH, "wb") as output_file:
    output.write(output_file)

print(f"\n✅ Done! Filled {matched_count}/{len(fields)} fields")
print(f"📄 Output saved to {OUTPUT_PATH}")

