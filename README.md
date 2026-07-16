# StudyFrame

> **Ask a school question. Get a step-by-step MP4 explainer video.**

StudyFrame is an AI-powered study application that takes any school question, analyzes it with Gemini AI, generates a visual explainer video complete with AI-generated images and narrated audio, and saves it to Google Drive — automatically.

---

## How It Works

```
You type a question
    |
    v
[FastAPI Backend]
    |
    v
[Gemini AI] --> Step-by-step explanation (JSON)
    |
    v
[Image Planner] --> Detailed image prompts per step
    |
    v
[Chrome Agent (Puppeteer)] --> Automates Meta AI to generate JPEGs
    |                          (Falls back to Leonardo AI API)
    v
[Video Assembler (MoviePy + Google TTS)] --> MP4 explainer video
    |
    v
[Google Drive Upload + Notion Log] --> Video link delivered to you
```

---

## Project Structure

```
studyframe/
|-- backend/                  # Python FastAPI backend
|   |-- main.py               # API entry point + pipeline orchestrator
|   |-- reasoning_engine.py   # Gemini AI explanation generator
|   |-- image_planner.py      # Image scene planner + Leonardo AI fallback
|   |-- video_assembler.py    # MoviePy + Google TTS video builder
|   |-- drive_uploader.py     # Google Drive upload + Notion logging
|
|-- agent/                    # Node.js Chrome automation agent
|   |-- chrome_agent.js       # Puppeteer agent (WebSocket server)
|   |-- package.json          # Node.js dependencies
|
|-- frontend/                 # React web UI
|   |-- src/
|       |-- App.jsx           # Main UI component
|
|-- requirements.txt          # Python dependencies
|-- .gitignore
|-- LICENSE
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python + FastAPI |
| AI Reasoning | Google Gemini 1.5 Pro |
| Image Planning | Gemini 1.5 Pro |
| Image Generation (Primary) | Meta AI (via Chrome/Puppeteer) |
| Image Generation (Fallback) | Leonardo AI REST API |
| Text-to-Speech | Google Cloud TTS (Neural2-D voice) |
| Video Assembly | MoviePy + ffmpeg |
| Chrome Automation | Puppeteer + puppeteer-extra-stealth |
| Frontend | React.js |
| Storage | Google Drive API |
| Study Log | Notion API |
| Agent Communication | WebSocket (ws) |

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/thukevn/studyframe.git
cd studyframe
```

### 2. Set up Python backend
```bash
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` folder:
```env
GEMINI_API_KEY=your_gemini_api_key
LEONARDO_API_KEY=your_leonardo_api_key
GOOGLE_SERVICE_ACCOUNT_JSON=path/to/service_account.json
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id
NOTION_API_TOKEN=your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id
CHROME_AGENT_WS=ws://localhost:8765
```

### 3. Set up Chrome Agent
```bash
cd agent
npm install
npm start
```

The agent will:
- Launch Chrome
- Navigate to Meta AI
- Start a WebSocket server on port 8765
- Wait for image generation requests from the backend

### 4. Start the backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 5. Start the frontend
```bash
cd frontend
npm install
npm start
```

Open `http://localhost:3000` in your browser.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| POST | `/submit` | Submit a question (returns job_id) |
| GET | `/status/{job_id}` | Poll job status |
| GET | `/jobs` | List all jobs |

### POST /submit
```json
{
  "question": "How do I solve a system of linear equations?",
  "subject": "math"
}
```

### Job Status Flow
`pending` -> `reasoning` -> `planning_images` -> `generating_images` -> `assembling_video` -> `uploading` -> `done`

---

## Supported Subjects
- Math
- Computer Science
- Biology
- Chemistry
- Physics
- History
- English
- Auto-detect (default)

---

## Environment Variables Reference

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `LEONARDO_API_KEY` | Leonardo AI API key (fallback image gen) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to Google service account JSON file |
| `GOOGLE_DRIVE_FOLDER_ID` | Google Drive folder ID for video storage |
| `NOTION_API_TOKEN` | Notion integration token |
| `NOTION_DATABASE_ID` | Notion database ID for study log |
| `CHROME_AGENT_WS` | WebSocket URL of the Chrome agent (default: ws://localhost:8765) |
| `WS_PORT` | Port for the Chrome agent WebSocket server (default: 8765) |
| `IMAGES_OUTPUT_DIR` | Local directory for saving agent-generated images |

---

## License

MIT License - see [LICENSE](LICENSE) for details.
