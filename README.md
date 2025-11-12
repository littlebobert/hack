# Paper Form Digitizer

React Native + FastAPI project that captures paper form photos and generates fillable digital versions by invoking the OpenAI Vision API.

## Architecture

- **Mobile/Web client (`apps/mobile`)** – Expo-managed React Native app that captures or uploads a photo, sends it to the backend, and renders the generated form schema as interactive inputs.
- **Backend (`backend`)** – FastAPI service that accepts image uploads, stores the original file, calls OpenAI’s Vision model to extract field structure, and returns a normalized JSON schema.
- **OpenAI Vision** – Uses the `responses.create` endpoint with `response_format=json_object` to guarantee structured output.

## Prerequisites

- Node.js 18+
- pnpm, npm, or yarn (pnpm recommended)
- Python 3.11+
- OpenAI API key with access to vision-capable models (e.g., `gpt-4.1-mini`)
- Expo CLI (`npm install -g expo-cli`) for local development

## Backend Setup

```bash
cd /Users/justin/dev/hack/backend
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env  # add your OpenAI API key and optional overrides
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Environment variables (prefixed with `FORMBUILDER_`):

- `OPENAI_API_KEY` (required)
- `OPENAI_MODEL` (defaults to `gpt-4.1-mini`)
- `OPENAI_BASE_URL` (optional, for Azure/OpenAI-compatible endpoints)
- `ALLOWED_ORIGINS` (JSON array for CORS)

The `/extract` endpoint accepts `multipart/form-data` with a single `file` field containing the image. The service stores uploads under `backend/storage/uploads/` and responds with a `FormDocument` JSON payload.

## Mobile/Web Client Setup

```bash
cd /Users/justin/dev/hack/apps/mobile
pnpm install  # or npm/yarn install
pnpm start    # launches Expo (press w for web, i for iOS, a for Android)
```

Key flows:

1. Tap **Capture Form** or **Upload Photo** to select an image.
2. The app sends the image as multipart form data to the backend.
3. Once the schema returns, the app renders a digital preview with text, checkbox, select, and other field types.

The backend URL defaults to `http://localhost:8000`. Override it via `app.json -> expo.extra.backendUrl` or set `EXPO_PUBLIC_BACKEND_URL` and read it with `process.env`.

## Next Steps

- Add persistence for generated schemas and filled responses (PostgreSQL + Prisma/SQLAlchemy).
- Provide a web editing experience for manual corrections.
- Implement PDF/CSV export based on completed responses.
- Introduce background job processing and confidence-based review queues for low-accuracy OCR outputs.