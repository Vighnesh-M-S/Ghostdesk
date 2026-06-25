import logging
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from backend.workflow import workflow
from backend.database import init_db, save_result, get_analytics, get_history

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GhostDesk API",
    description="Privacy-first AI Support Employee",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("GhostDesk API ready")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "GhostDesk"}


@app.post("/process")
async def process_email(
    email_text: str = Form(...),
    attachments: Optional[List[UploadFile]] = File(default=None),
):
    """Run the full GhostDesk multi-agent workflow on a support email."""
    try:
        attachment_data = []
        if attachments:
            for f in attachments:
                if f.filename:
                    content = await f.read()
                    ext = Path(f.filename).suffix.lstrip(".").lower()
                    attachment_data.append({"filename": f.filename, "type": ext, "content": content})

        initial_state: dict = {
            "email_text": email_text,
            "redacted_email": "",
            "intent": "",
            "intent_confidence": 0.0,
            "attachments": attachment_data,
            "attachment_summary": "",
            "verification_result": "",
            "risk_flags": [],
            "risk_score": 0.0,
            "recommended_action": "",
            "resolution_summary": "",
            "requires_human_review": False,
            "final_output": {},
            "processing_errors": [],
        }

        result = workflow.invoke(initial_state)

        # Persist (drop binary before saving)
        save_result(result)

        # Strip binary content from response
        response_data = result.get("final_output") or result
        if isinstance(response_data, dict) and "attachments" in response_data:
            for att in response_data["attachments"]:
                att.pop("content", None)

        return {"success": True, "data": response_data}

    except Exception as exc:
        logger.error("Processing error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/analytics")
async def analytics():
    return get_analytics()


@app.get("/history")
async def history(limit: int = 50):
    return get_history(limit)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
