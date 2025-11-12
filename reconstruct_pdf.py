"""
LLMに画像を解析させて、内容を完全に再構築したPDFを生成
"""
import json
import base64
from pathlib import Path
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io

load_dotenv()
client = OpenAI()

INPUT_PATH = Path("questionnaire.jpg")
OUTPUT_PATH = Path("questionnaire_reconstructed.pdf")

print("🔍 Analyzing and reconstructing image with Vision API...")

# 画像を読み込んでbase64エンコード
img = Image.open(INPUT_PATH)
img_width, img_height = img.size

# base64エンコード（高品質）
img_buffer = io.BytesIO()
img.save(img_buffer, format='JPEG', quality=95)
image_data = base64.b64encode(img_buffer.getvalue()).decode()

# Vision APIで画像を完全に解析
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": """Completely analyze this document image and extract ALL content.

For each element, provide:
1. Type: "title", "heading", "label", "field_line", "checkbox", "text"
2. Content: The actual text
3. Position: Rough position as percentage (0-100) of page width/height
4. Style: font_size (in points), bold, alignment

Return detailed JSON:
{
  "document_type": "questionnaire form",
  "title": "クリニック問診票",
  "elements": [
    {"type": "title", "content": "クリニック問診票", "x_pct": 50, "y_pct": 5, "font_size": 18, "bold": true, "align": "center"},
    {"type": "heading", "content": "【基本情報】", "x_pct": 10, "y_pct": 15, "font_size": 14, "bold": true},
    {"type": "label", "content": "お名前", "x_pct": 10, "y_pct": 20, "font_size": 12},
    {"type": "field_line", "x_pct": 30, "y_pct": 20, "width_pct": 60},
    ...
  ]
}

Extract EVERYTHING you can see in the image."""
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
content_json = response.choices[0].message.content.strip()

# マークダウンのコードブロックを除去
if content_json.startswith("```"):
    lines = content_json.split("\n")
    content_json = "\n".join(lines[1:-1])

try:
    content = json.loads(content_json)
except:
    print("⚠️ Failed to parse JSON. Saving raw output...")
    Path("reconstruction_output.txt").write_text(content_json)
    print("Saved to reconstruction_output.txt")
    exit(1)

print("\n📋 Extracted content:")
print(json.dumps(content, indent=2, ensure_ascii=False))

# 日本語フォント設定
font_name = 'Helvetica'
try:
    hiragino_path = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
    if Path(hiragino_path).exists():
        pdfmetrics.registerFont(TTFont('Japanese', hiragino_path, subfontIndex=0))
        font_name = 'Japanese'
        print("\n✓ Using Hiragino font")
except:
    print("\n⚠️ Using Helvetica font")

# PDFを再構築
print(f"\n📄 Reconstructing PDF...")

page_width, page_height = A4
c = canvas.Canvas(str(OUTPUT_PATH), pagesize=A4)

# 各要素を描画
for elem in content.get("elements", []):
    elem_type = elem["type"]
    content_text = elem.get("content", "")
    x = (elem["x_pct"] / 100) * page_width
    y = page_height - ((elem["y_pct"] / 100) * page_height)  # PDFは下から上
    font_size = elem.get("font_size", 12)
    
    if elem_type in ["title", "heading", "label", "text"]:
        # テキストを描画
        c.setFont(font_name, font_size)
        
        align = elem.get("align", "left")
        if align == "center":
            c.drawCentredString(x, y, content_text)
        elif align == "right":
            c.drawRightString(x, y, content_text)
        else:
            c.drawString(x, y, content_text)
    
    elif elem_type == "field_line":
        # フィールドラインを描画
        width = (elem.get("width_pct", 50) / 100) * page_width
        c.line(x, y, x + width, y)
    
    elif elem_type == "checkbox":
        # チェックボックスを描画
        size = 10
        c.rect(x, y - size, size, size, stroke=1, fill=0)
        # ラベルがあれば描画
        if content_text:
            c.setFont(font_name, font_size)
            c.drawString(x + size + 5, y - size + 2, content_text)

# メタデータ
c.setTitle(content.get("document_type", "Document"))
c.setCreator("PDF Reconstructor (powered by OpenAI)")

c.save()

print(f"\n✅ Done!")
print(f"📄 Output: {OUTPUT_PATH}")
print(f"💡 Document type: {content.get('document_type')}")
print(f"📝 Elements reconstructed: {len(content.get('elements', []))}")

