from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import uuid
import os
from datetime import datetime

from reasoning_engine import ReasoningEngine
from image_planner import ImagePlanner
from video_assembler import VideoAssembler
from drive_uploader import DriveUploader

app = FastAPI(
    title="StudyFrame API",
    description="AI-powered study explainer video generator",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-memory job tracker ---
jobs = {}

class QuestionRequest(BaseModel):
    question: str
    subject: str = "auto"  # auto-detect or specify: math, cs, biology, etc.

class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, reasoning, generating_images, assembling_video, done, error
    message: str = ""
    video_url: str = ""
    notion_url: str = ""

@app.get("/")
async def root():
    return {"message": "StudyFrame API is running", "version": "1.0.0"}

@app.post("/submit", response_model=JobStatus)
async def submit_question(request: QuestionRequest):
    """
    Main endpoint: receives a study question and kicks off the full pipeline.
    Returns a job_id to poll for status.
    """
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "message": "Job queued",
        "video_url": "",
        "notion_url": "",
        "created_at": datetime.now().isoformat()
    }

    # Run pipeline asynchronously
    asyncio.create_task(run_pipeline(job_id, request.question, request.subject))

    return JobStatus(
        job_id=job_id,
        status="pending",
        message="Your question has been submitted. Processing started."
    )

@app.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    """Poll this endpoint to track job progress."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        message=job["message"],
        video_url=job.get("video_url", ""),
        notion_url=job.get("notion_url", "")
    )

@app.get("/jobs")
async def list_jobs():
    """List all jobs and their statuses."""
    return jobs

async def run_pipeline(job_id: str, question: str, subject: str):
    """
    Full StudyFrame pipeline:
    1. Reasoning Engine  -> step-by-step explanation
    2. Image Planner     -> image prompts per step
    3. Chrome Agent      -> generate images via Meta AI (triggered via WebSocket)
    4. Video Assembler   -> stitch images + TTS audio into MP4
    5. Drive Uploader    -> save to Google Drive + log to Notion
    """
    try:
        # Step 1: Reasoning
        jobs[job_id]["status"] = "reasoning"
        jobs[job_id]["message"] = "AI is analyzing your question..."

        engine = ReasoningEngine()
        explanation = await engine.explain(question, subject)

        # Step 2: Image Planning
        jobs[job_id]["status"] = "planning_images"
        jobs[job_id]["message"] = "Planning visual scenes for each step..."

        planner = ImagePlanner()
        image_plan = await planner.plan(explanation)

        # Step 3: Chrome Agent triggers image generation
        # The agent listens on ws://localhost:8765
        # We send it prompts, it returns saved image paths
        jobs[job_id]["status"] = "generating_images"
        jobs[job_id]["message"] = "Generating images via Meta AI..."

        image_paths = await trigger_chrome_agent(job_id, image_plan)

        # Step 4: Assemble video
        jobs[job_id]["status"] = "assembling_video"
        jobs[job_id]["message"] = "Assembling explainer video..."

        assembler = VideoAssembler()
        output_path = await assembler.assemble(
            explanation=explanation,
            image_paths=image_paths,
            job_id=job_id
        )

        # Step 5: Upload to Google Drive + log to Notion
        jobs[job_id]["status"] = "uploading"
        jobs[job_id]["message"] = "Uploading video to Google Drive..."

        uploader = DriveUploader()
        result = await uploader.upload(output_path, question, job_id)

        jobs[job_id]["status"] = "done"
        jobs[job_id]["message"] = "Your explainer video is ready!"
        jobs[job_id]["video_url"] = result["drive_url"]
        jobs[job_id]["notion_url"] = result.get("notion_url", "")

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["message"] = f"Pipeline error: {str(e)}"

async def trigger_chrome_agent(job_id: str, image_plan: list) -> list:
    """
    Sends image prompts to the Chrome Automation Agent via WebSocket.
    The agent (chrome_agent.js) handles browser automation to Meta AI.
    Returns list of local image file paths.
    """
    import websockets
    import json

    image_paths = []
    agent_url = os.getenv("CHROME_AGENT_WS", "ws://localhost:8765")

    try:
        async with websockets.connect(agent_url) as ws:
            for scene in image_plan:
                payload = {
                    "job_id": job_id,
                    "scene_id": scene["scene_id"],
                    "prompt": scene["prompt"]
                }
                await ws.send(json.dumps(payload))
                response = await asyncio.wait_for(ws.recv(), timeout=120)
                result = json.loads(response)

                if result["status"] == "success":
                    image_paths.append(result["file_path"])
                else:
                    # Fallback: use Leonardo AI API directly
                    from image_planner import generate_image_fallback
                    path = await generate_image_fallback(scene["prompt"], scene["scene_id"], job_id)
                    image_paths.append(path)
    except Exception:
        # If agent is offline, use Leonardo AI for all images
        from image_planner import generate_image_fallback
        for scene in image_plan:
            path = await generate_image_fallback(scene["prompt"], scene["scene_id"], job_id)
            image_paths.append(path)

    return image_paths

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
