# Questionnaire OCR API

FastAPI service that accepts a questionnaire photo upload, forwards it to OpenAI's OCR/vision models, and returns structured JSON with question/answer pairs.

## Getting Started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your OpenAI credentials (the OCR call requires a vision-capable model such as `gpt-4o` or `gpt-4o-mini`):

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_VISION_MODEL="gpt-4o-mini"  # optional override
```

Run the server:

```bash
uvicorn app.main:app --reload --port 8000
```

## API

- `GET /health` – heartbeat.
- `POST /api/v1/questionnaires/parse` – multipart form upload (`file` field). Optional query param `include_debug=true` adds OCR debug blocks.

Sample `curl`:

```bash
curl -X POST "http://localhost:8000/api/v1/questionnaires/parse?include_debug=true" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@./sample_form.jpg"
```

Response:

```json
{
  "questions": [
    {"question": "1. Full name", "answer": "Jane Doe"},
    {"question": "2. Preferred contact method", "answer": "Email"}
  ],
  "raw_text": "1. Full name ...",
  "debug_blocks": [
    {"line": "1. Full name", "confidence": 0.91}
  ]
}
```
