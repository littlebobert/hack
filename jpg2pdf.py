"""
LLMを使って画像を解析し、最適なPDF設定で変換するスクリプト
"""
import json
import base64
from pathlib import Path
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io

load_dotenv()
client = OpenAI()

INPUT_PATH = Path("questionnaire.jpg")
OUTPUT_PATH = Path("questionnaire_smart.pdf")

print("🔍 Analyzing image with Vision API...")

# 画像を読み込んでbase64エンコード
img = Image.open(INPUT_PATH)
img_width, img_height = img.size

# サムネイルを作成（API送信用に圧縮）
thumbnail = img.copy()
thumbnail.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

# base64エンコード
img_buffer = io.BytesIO()
thumbnail.save(img_buffer, format='JPEG', quality=85)
image_data = base64.b64encode(img_buffer.getvalue()).decode()

# Vision APIで画像を解析して最適な設定を取得
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""Analyze this image and recommend optimal PDF settings.

Image size: {img_width}x{img_height} pixels

Provide recommendations for:
1. PDF page size (e.g., A4, Letter, or custom dimensions in points)
2. Image orientation (portrait or landscape)
3. Should the image be cropped or have margins?
4. Recommended compression quality (1-100)
5. Image description (what is this document?)

Return ONLY valid JSON:
{{
  "page_size": "A4",
  "orientation": "portrait",
  "margins": {{"top": 0, "bottom": 0, "left": 0, "right": 0}},
  "quality": 85,
  "description": "Japanese clinic questionnaire form",
  "recommendations": "This is a form that should preserve all details..."
}}"""
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                }
            ]
        }
    ]
)

# レスポンスをパース
settings_json = response.choices[0].message.content.strip()

# マークダウンのコードブロックを除去
if settings_json.startswith("```"):
    lines = settings_json.split("\n")
    settings_json = "\n".join(lines[1:-1])

settings = json.loads(settings_json)

print("\n📋 LLM Recommendations:")
print(json.dumps(settings, indent=2, ensure_ascii=False))

# PDF設定を適用
from reportlab.lib.pagesizes import A4, LETTER

# ページサイズを決定
if settings["page_size"] == "A4":
    page_size = A4
elif settings["page_size"] == "Letter":
    page_size = LETTER
else:
    # カスタムサイズ（画像のアスペクト比を保持）
    aspect_ratio = img_width / img_height
    page_size = (595, 595 / aspect_ratio)  # A4幅をベース

if settings["orientation"] == "landscape":
    page_size = (page_size[1], page_size[0])

print(f"\n📄 Creating PDF...")
print(f"   Page size: {settings['page_size']} ({page_size[0]:.1f} x {page_size[1]:.1f} points)")
print(f"   Orientation: {settings['orientation']}")
print(f"   Quality: {settings['quality']}%")

# PDFを作成
c = canvas.Canvas(str(OUTPUT_PATH), pagesize=page_size)

# 画像を配置（マージン考慮）
margins = settings["margins"]
x = margins["left"]
y = margins["bottom"]
width = page_size[0] - margins["left"] - margins["right"]
height = page_size[1] - margins["top"] - margins["bottom"]

# 画像を高品質で保存
temp_img = io.BytesIO()
img.save(temp_img, format='JPEG', quality=settings["quality"])
temp_img.seek(0)

c.drawImage(
    ImageReader(temp_img),
    x, y,
    width=width,
    height=height,
    preserveAspectRatio=True,
    anchor='c'
)

# メタデータを追加
c.setTitle(settings.get("description", "Document"))
c.setSubject(settings.get("recommendations", ""))
c.setCreator("Smart JPG to PDF Converter (powered by OpenAI)")

c.save()

print(f"\n✅ Done!")
print(f"📄 Output: {OUTPUT_PATH}")
print(f"💡 Description: {settings['description']}")
print(f"📝 Notes: {settings['recommendations']}")

