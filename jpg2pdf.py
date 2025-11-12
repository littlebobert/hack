from PIL import Image
import img2pdf
from pathlib import Path

# === 入力と出力ファイルパス ===
input_path = Path("questionnaire.jpg")
output_path = Path("questionnaire_converted.pdf")

# === 画像を開く ===
img = Image.open(input_path).convert("RGB")

# === PDFとして保存 ===
with open(output_path, "wb") as f:
    f.write(img2pdf.convert(img.filename))

print(f"✅ Converted: {input_path.name} → {output_path.name}")
