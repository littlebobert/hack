import json
import base64
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

# === 1️⃣ Visionでフォーム欄を解析（キャッシュ使用） ===
if FIELDS_CACHE_PATH.exists():
    print("📂 Loading cached field positions from fields_cache.json")
    fields = json.loads(FIELDS_CACHE_PATH.read_text())
else:
    print("🔍 Analyzing form layout with Vision API (this costs money)...")
    
    # 画像をbase64エンコード
    with open(FORM_PATH, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    
    vision_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": (
                         "You are analyzing a questionnaire form image. "
                         "Detect all empty input fields (like name, age, gender, etc.) "
                         "and return JSON array like: "
                         "[{\"field\":\"name\",\"x\":120,\"y\":240,\"width\":300,\"height\":40}, ...]. "
                         "Coordinates should be in pixels relative to the image top-left corner."
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
        fields = json.loads(fields_json)
    except Exception as e:
        print("⚠️ Could not parse model output as JSON. Raw output:\n", fields_json)
        raise e
    
    # キャッシュに保存
    FIELDS_CACHE_PATH.write_text(json.dumps(fields, indent=2))
    print(f"💾 Saved field positions to {FIELDS_CACHE_PATH}")

print("Detected fields:")
print(json.dumps(fields, indent=2))

# === 2️⃣ 回答データをロード ===
answers = json.loads(ANSWERS_PATH.read_text())

# === 3️⃣ Pillowで描画 ===
print("✍️  Drawing answers onto image...")

img = Image.open(FORM_PATH)
draw = ImageDraw.Draw(img)

# より大きく見やすいフォントを使用
try:
    # macOSの標準フォント
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
except:
    # フォントが見つからない場合はデフォルト
    font = ImageFont.load_default()
    print("⚠️  Using default font (may be small)")

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
for f in fields:
    field_name = f["field"]
    text = match_field_name(field_name, answers)
    
    if text is not None:
        text = str(text)
        x, y = f["x"], f["y"]
        draw.text((x, y), text, fill="black", font=font)
        print(f"  ✓ {field_name}: '{text}' at ({x}, {y})")
        matched_count += 1
    else:
        print(f"  ✗ {field_name}: No matching answer found")

img.save(OUTPUT_PATH)
print(f"\n✅ Done! Filled {matched_count}/{len(fields)} fields")
print(f"📄 Output saved to {OUTPUT_PATH}")
