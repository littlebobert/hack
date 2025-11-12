import json
import base64
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI
from dotenv import load_dotenv

# === 設定 ===
load_dotenv()
client = OpenAI()

FORM_PATH = Path("questionnaire.jpg")
ANSWERS_PATH = Path("answers.json")
FIELDS_CACHE_PATH = Path("fields_cache.json")  # Vision API結果のキャッシュ
OUTPUT_PATH = Path("filled_form.jpg")

# コマンドライン引数チェック
FORCE_REFRESH = "--refresh" in sys.argv or "-r" in sys.argv

# === 使い方表示 ===
if "--help" in sys.argv or "-h" in sys.argv:
    print("""
使い方:
  python gen_pic.py           # キャッシュがあればそれを使用
  python gen_pic.py --refresh # Vision APIで座標を再取得（お金がかかります）
  python gen_pic.py -r        # --refreshの短縮形
  python gen_pic.py --help    # このヘルプを表示

ファイル:
  - questionnaire.jpg    : 入力フォーム画像
  - answers.json         : 埋め込む回答データ
  - fields_cache.json    : Vision APIで取得した座標（手動編集可能）
  - filled_form.jpg      : 出力画像（赤い点=テキスト位置）
    """)
    sys.exit(0)

# === 1️⃣ Visionでフォーム欄を解析（キャッシュ使用） ===
if FIELDS_CACHE_PATH.exists() and not FORCE_REFRESH:
    print("📂 Loading cached field positions from fields_cache.json")
    print("   (座標を再取得する場合: python gen_pic.py --refresh)")
    fields = json.loads(FIELDS_CACHE_PATH.read_text())
else:
    if FORCE_REFRESH:
        print("🔄 Force refreshing field positions...")
    print("🔍 Analyzing form layout with Vision API (this costs money)...")
    
    # 画像をbase64エンコード
    with open(FORM_PATH, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    
    # 画像サイズを取得
    img_temp = Image.open(FORM_PATH)
    img_width, img_height = img_temp.size
    img_temp.close()
    
    vision_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": (
                         f"Analyze this Japanese questionnaire form image (size: {img_width}x{img_height}px). "
                         f"For each input field, detect:\n"
                         f"1. Field name (e.g., 'name', 'date_of_birth', 'gender', 'phone', 'address', etc.)\n"
                         f"2. Field type: 'text' or 'checkbox'\n"
                         f"3. For TEXT fields: x,y coordinates where to write the answer, and recommended font_size in pixels\n"
                         f"4. For CHECKBOX fields: list of checkbox options with their coordinates\n\n"
                         f"Important:\n"
                         f"- '性別 (Gender)' with '□男性 □女性 □その他' is a CHECKBOX field\n"
                         f"- Text input fields (like お名前, 生年月日) are TEXT fields\n"
                         f"- Font size should be appropriate for the field size (e.g., 30-50px for normal fields)\n\n"
                         f"Return ONLY valid JSON in this format:\n"
                         f'{{\n'
                         f'  "fields": [\n'
                         f'    {{"field":"name", "type":"text", "x":400, "y":350, "font_size":45}},\n'
                         f'    {{"field":"gender", "type":"checkbox", "options":[\n'
                         f'      {{"label":"male", "x":400, "y":410}},\n'
                         f'      {{"label":"female", "x":500, "y":410}},\n'
                         f'      {{"label":"other", "x":600, "y":410}}\n'
                         f'    ]}}\n'
                         f'  ]\n'
                         f'}}\n\n'
                         f"Be precise with pixel coordinates."
                     )},
                    {"type": "image_url",
                     "image_url": {
                         "url": f"data:image/jpeg;base64,{image_data}"
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
        # "fields"キーがある場合はそれを使用、なければそのまま使用
        fields = response_data.get("fields", response_data) if isinstance(response_data, dict) else response_data
    except Exception as e:
        print("⚠️ Could not parse model output as JSON. Raw output:\n", fields_json)
        raise e
    
    # キャッシュに保存
    FIELDS_CACHE_PATH.write_text(json.dumps(fields, indent=2, ensure_ascii=False))
    print(f"💾 Saved field positions to {FIELDS_CACHE_PATH}")

print("Detected fields:")
print(json.dumps(fields, indent=2))

# === 2️⃣ 回答データをロード ===
answers = json.loads(ANSWERS_PATH.read_text())

# === 3️⃣ Pillowで描画 ===
print("\n✍️  Drawing answers onto image...")

img = Image.open(FORM_PATH)
draw = ImageDraw.Draw(img)

# フォントの読み込み関数（サイズ指定可能）
def load_font(size=40):
    """指定されたサイズのフォントを読み込む"""
    try:
        # macOSの標準フォント（日本語対応）
        return ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", size)
    except:
        try:
            return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
        except:
            return ImageFont.load_default()

# チェックマークを描画する関数
def draw_checkbox_mark(draw, x, y, size=30):
    """チェックボックスにチェックマークを描画"""
    # ✓マークを線で描画
    offset = size // 4
    draw.line([x, y, x + offset, y + offset], fill="black", width=4)
    draw.line([x + offset, y + offset, x + size, y - offset], fill="black", width=4)

# フィールド名の柔軟なマッチング（複数形/単数形を考慮）
def match_field_name(field_name, answers_dict):
    """フィールド名を柔軟にマッチング"""
    field_lower = field_name.lower()
    
    # 完全一致を試す
    if field_lower in answers_dict:
        return answers_dict[field_lower]
    
    # 単数形/複数形の変換を試す
    if field_lower.endswith('s'):
        singular = field_lower[:-1]
        if singular in answers_dict:
            return answers_dict[singular]
    else:
        plural = field_lower + 's'
        if plural in answers_dict:
            return answers_dict[plural]
    
    # 部分一致を試す（例: "hobby" in "hobbies"）
    for key in answers_dict:
        if key in field_lower or field_lower in key:
            return answers_dict[key]
    
    return None

matched_count = 0
print(f"Image size: {img.size}")

for f in fields:
    field_name = f.get("field", "unknown")
    field_type = f.get("type", "text")
    
    # answers.jsonから値を取得
    answer_value = match_field_name(field_name, answers)
    
    if field_type == "text":
        # === テキストフィールドの処理 ===
        if answer_value is not None:
            text = str(answer_value)
            x, y = f["x"], f["y"]
            font_size = f.get("font_size", 40)
            
            # フォントを読み込み
            font = load_font(font_size)
            
            # デバッグ: 座標に小さな赤い点を描画
            draw.ellipse([x-5, y-5, x+5, y+5], fill="red", outline="red")
            
            # テキストを描画
            draw.text((x, y), text, fill=(0, 0, 0), font=font)
            print(f"  ✓ TEXT {field_name}: '{text}' at ({x}, {y}), size={font_size}px")
            matched_count += 1
        else:
            print(f"  ✗ TEXT {field_name}: No matching answer found")
            if "x" in f and "y" in f:
                x, y = f["x"], f["y"]
                draw.ellipse([x-5, y-5, x+5, y+5], fill="blue", outline="blue")
    
    elif field_type == "checkbox":
        # === チェックボックスフィールドの処理 ===
        if answer_value is not None and "options" in f:
            answer_lower = str(answer_value).lower()
            
            # チェックボックスのオプションをループ
            checked_any = False
            for option in f["options"]:
                option_label = option.get("label", "").lower()
                option_x, option_y = option["x"], option["y"]
                
                # 値がマッチするかチェック
                is_match = (
                    answer_lower == option_label or
                    answer_lower in option_label or
                    option_label in answer_lower
                )
                
                if is_match:
                    # チェックマークを描画
                    draw_checkbox_mark(draw, option_x, option_y, size=25)
                    # デバッグ: 緑の点を描画
                    draw.ellipse([option_x-5, option_y-5, option_x+5, option_y+5], fill="green", outline="green")
                    print(f"  ✓ CHECKBOX {field_name}: checked '{option_label}' at ({option_x}, {option_y})")
                    checked_any = True
                    matched_count += 1
                    break
            
            if not checked_any:
                print(f"  ⚠️  CHECKBOX {field_name}: value '{answer_value}' didn't match any option")
        else:
            print(f"  ✗ CHECKBOX {field_name}: No matching answer or missing options")
    
    else:
        print(f"  ⚠️  Unknown field type: {field_type}")

img.save(OUTPUT_PATH, quality=95)
print(f"\n✅ Done! Filled {matched_count}/{len(fields)} fields")
print(f"📄 Output saved to {OUTPUT_PATH}")
print(f"💡 Red dots = text, Green dots = checkbox checked, Blue dots = no match")
