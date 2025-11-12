from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Japanese TrueType font (download from Google Fonts)
pdfmetrics.registerFont(TTFont('NotoSansJP', 'NotoSansJP-VariableFont_wght.ttf'))

# Create new PDF
file_path = "japanese_clinic_questionnaire_fixed.pdf"
doc = SimpleDocTemplate(file_path, pagesize=A4)

# Use Japanese font in all styles
styles = getSampleStyleSheet()
for s in styles.byName.values():
    s.fontName = 'NotoSansJP'
styles.add(ParagraphStyle(name='Japanese', fontName='NotoSansJP', fontSize=11))

story = []

# Title
story.append(Paragraph("クリニック問診票（Clinic Questionnaire）", styles["Title"]))
story.append(Spacer(1, 20))

# Basic Information
story.append(Paragraph("<b>【基本情報】</b>", styles["Heading2"]))
data_basic = [
    ["お名前（Name）", "　　　　　　　　　　　　　　　　　　　　　　"],
    ["生年月日（Date of Birth）", "　　　　　　　　　　　　　　　　　　　　　　"],
    ["性別（Gender）", "□ 男性　□ 女性　□ その他"],
    ["電話番号（Phone）", "　　　　　　　　　　　　　　　　　　　　　　"],
    ["住所（Address）", "　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　"]
]
table_basic = Table(data_basic, colWidths=[160, 320])
table_basic.setStyle(
    TableStyle(
        [
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'NotoSansJP'),
        ]
    )
)
story.append(table_basic)
story.append(Spacer(1, 15))

# Reason for Visit
story.append(Paragraph("<b>【来院の目的 / 主な症状】</b>", styles["Heading2"]))
story.append(Paragraph("ご来院の理由をお書きください。", styles["Normal"]))
story.append(Spacer(1, 5))
story.append(Paragraph("_________________________________________________________", styles["Normal"]))
story.append(Spacer(1, 15))

# Medical History
story.append(Paragraph("<b>【既往歴・服薬・アレルギー】</b>", styles["Heading2"]))
data_history = [
    ["現在治療中の病気（Ongoing Conditions）", "　　　　　　　　　　　　　　　　　　　　　　　　　"],
    ["現在服用している薬（Current Medication）", "　　　　　　　　　　　　　　　　　　　　　　　　　"],
    ["薬・食べ物のアレルギー（Allergies）", "　　　　　　　　　　　　　　　　　　　　　　　　　"]
]
table_history = Table(data_history, colWidths=[220, 260])
table_history.setStyle(
    TableStyle(
        [
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'NotoSansJP'),
        ]
    )
)
story.append(table_history)
story.append(Spacer(1, 15))

# Lifestyle
story.append(Paragraph("<b>【生活習慣】</b>", styles["Heading2"]))
story.append(Paragraph("喫煙（Smoking）: □ 吸う　□ 吸わない　　飲酒（Alcohol）: □ 飲む　□ 飲まない", styles["Normal"]))
story.append(Spacer(1, 10))
story.append(Paragraph("睡眠時間（Average Sleep Hours）: ______ 時間", styles["Normal"]))
story.append(Spacer(1, 15))

# Consent
story.append(Paragraph("<b>【同意書】</b>", styles["Heading2"]))
story.append(Paragraph("本問診票の内容は、診療の目的のみに使用します。", styles["Normal"]))
story.append(Spacer(1, 10))
story.append(Paragraph("署名（Signature）: _________________________　　日付（Date）: ___________________", styles["Normal"]))

# Build PDF
doc.build(story)
print("✅ PDF created successfully:", file_path)
