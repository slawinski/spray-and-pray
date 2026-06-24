from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import subprocess
import os
import json as json_mod
from pathlib import Path
import logging
from cv_optimizer.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CV Optimizer Local API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (LinkedIn, etc)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class TrackRequest(BaseModel):
    company: str
    role: str
    jd: str
    url: str = None

def send_discord_notification(title: str, description: str, color: int, url: str = None):
    webhook_url = settings.discord_webhook_url
    if not webhook_url:
        logger.warning("Discord webhook URL not configured. Skipping push notification.")
        return
        
    import requests
    
    embed = {
        "title": title,
        "description": description,
        "color": color
    }
    
    if url:
        embed["url"] = url
        
    payload = {
        "content": "@everyone",
        "embeds": [embed]
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Discord notification sent successfully.")
    except Exception as e:
        logger.warning(f"Failed to send Discord notification: {e}")

def run_cv_optimizer(company: str, role: str, jd_text: str, job_url: str = None):
    import tempfile
    temp_jd = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    temp_jd.write(jd_text)
    temp_jd.close()
    temp_jd_path = Path(temp_jd.name)
    
    try:
        logger.info(f"Triggering tracking pipeline for {company} - {role}")
        from cv_optimizer.tracker import track
        app_id = track(company, role, str(temp_jd_path), job_url=job_url)
        
        logger.info(f"Optimization success for app #{app_id}")
        os.system(f"""osascript -e 'display notification "Optimization complete for {role} at {company}!" with title "✅ CV Optimizer"'""")
        
        discord_desc = f"Successfully generated tailored CV for **{role}** at **{company}**.\nReady in `applications/`."
        if job_url:
            discord_desc += f"\n\n🔗 [View Job Posting]({job_url})"
        
        send_discord_notification(
            title="✅ CV Generated (Click to open Finder)",
            description=discord_desc,
            color=0x00FF00,
            url=job_url or f"http://localhost:8000/api/open/{app_id}"
        )
            
    except Exception as e:
        logger.error(f"Error executing optimization: {e}")
        os.system(f"""osascript -e 'display notification "Error executing command." with title "❌ CV Optimizer"'""")
        send_discord_notification(
            title="❌ CV Generation Failed",
            description=f"Failed to generate CV for **{role}** at **{company}**.\nError: `{str(e)}`",
            color=0xFF0000
        )
    finally:
        if temp_jd_path.exists():
            temp_jd_path.unlink()

@app.post("/api/track")
async def track_application(request: TrackRequest, background_tasks: BackgroundTasks):
    if not request.company or not request.role or not request.jd:
        raise HTTPException(status_code=400, detail="Missing required fields")

    from cv_optimizer import db
    existing = db.find_application(request.company, request.role)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Already tracked — Application #{existing['id']}: {existing['company']} — {existing['role']}"
        )

    # We run the optimization in the background so the extension UI returns immediately
    background_tasks.add_task(run_cv_optimizer, request.company, request.role, request.jd, request.url)
    
    return {"status": "success", "message": f"Tracking initiated for {request.company} - {request.role}"}


class AnswerRequest(BaseModel):
    question_id: int
    answer_text: str = ""
    code: str = ""


@app.post("/api/interview/{app_id}/start")
async def start_interview(app_id: int):
    from cv_optimizer import db as db_mod
    from cv_optimizer.interview import InterviewGenerator
    import webbrowser

    app_data = db_mod.get_application(app_id)
    if not app_data:
        raise HTTPException(status_code=404, detail="Application not found")

    existing = db_mod.get_in_progress_session(app_id)
    if existing:
        url = f"http://localhost:8000/interview/{existing['id']}"
        webbrowser.open(url)
        return {
            "session_id": existing["id"],
            "session_url": url,
            "resumed": True,
        }

    generator = InterviewGenerator()
    result = generator.generate(app_id)
    session_id = result["session_id"]
    url = f"http://localhost:8000/interview/{session_id}"
    webbrowser.open(url)

    return {
        "session_id": session_id,
        "session_url": url,
    }


@app.get("/interview/{session_id}", response_class=HTMLResponse)
async def interview_page(request: Request, session_id: int):
    from cv_optimizer import db as db_mod

    session = db_mod.get_interview_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    questions = json_mod.loads(session["questions_json"])
    answers = json_mod.loads(session["answers_json"] or "[]")

    app_data = db_mod.get_application(session["application_id"])
    company = str(app_data[1]) if app_data else "Unknown"
    role = str(app_data[2]) if app_data else "Unknown"

    return templates.TemplateResponse(
        request=request,
        name="interview.html",
        context={
            "session_id": session_id,
            "company": company,
            "role": role,
            "questions": questions,
            "answers": answers,
            "evaluated": session["completed_at"] is not None,
        },
    )


@app.post("/api/interview/{session_id}/answer")
async def save_answer(session_id: int, request: AnswerRequest):
    from cv_optimizer import db as db_mod

    session = db_mod.get_interview_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["completed_at"] is not None:
        raise HTTPException(status_code=400, detail="Session already evaluated")

    answers = json_mod.loads(session["answers_json"] or "[]")
    existing = [a for a in answers if a["question_id"] != request.question_id]
    existing.append({
        "question_id": request.question_id,
        "answer_text": request.answer_text,
        "code": request.code,
    })
    db_mod.save_interview_answer(session_id, json_mod.dumps(existing))

    return {"ok": True}


@app.post("/api/interview/{session_id}/evaluate")
async def evaluate_interview(session_id: int):
    from cv_optimizer import db as db_mod
    from cv_optimizer.interview import InterviewEvaluator

    session = db_mod.get_interview_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["completed_at"] is not None:
        raise HTTPException(status_code=400, detail="Session already evaluated")

    evaluator = InterviewEvaluator()
    result = evaluator.evaluate(session_id)

    return result


@app.get("/api/interview/{session_id}/report", response_class=HTMLResponse)
async def interview_report_page(request: Request, session_id: int):
    from cv_optimizer import db as db_mod

    session = db_mod.get_interview_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    if session["completed_at"] is None:
        raise HTTPException(status_code=400, detail="Session not yet evaluated")

    app_data = db_mod.get_application(session["application_id"])
    company = str(app_data[1]) if app_data else "Unknown"
    role = str(app_data[2]) if app_data else "Unknown"

    evaluations = json_mod.loads(session["scores_json"] or "[]")
    readiness_score = session["readiness_score"]
    report_text = session["report_text"] or ""

    return templates.TemplateResponse(
        request=request,
        name="interview_report.html",
        context={
            "session_id": session_id,
            "company": company,
            "role": role,
            "evaluations": evaluations,
            "readiness_score": readiness_score,
            "report_text": report_text,
        },
    )


@app.get("/api/interview/{app_id}/latest")
async def latest_readiness(app_id: int):
    from cv_optimizer import db as db_mod

    score = db_mod.get_latest_readiness(app_id)
    return {"app_id": app_id, "readiness_score": score}


@app.get("/api/open/{app_id}", response_class=HTMLResponse)
async def open_in_finder(app_id: int):
    from cv_optimizer import db
    db.init_db()
    app_data = db.get_application(app_id)
    if not app_data or not app_data[4]:
        raise HTTPException(status_code=404, detail="Application or CV not found")
    
    cv_path = app_data[4]
    abs_path = os.path.abspath(cv_path)
    
    if os.path.exists(abs_path):
        # Reveal file in Finder
        subprocess.run(["open", "-R", abs_path])
        return HTMLResponse("""
        <html>
            <head><title>Opened!</title></head>
            <body style="font-family: sans-serif; text-align: center; margin-top: 50px;">
                <h2>✅ Opened in Finder!</h2>
                <p>You can safely close this tab now.</p>
                <script>
                    // Attempt to close the window automatically
                    setTimeout(function() { window.close(); }, 1500);
                </script>
            </body>
        </html>
        """)
    else:
        raise HTTPException(status_code=404, detail="File does not exist on disk")

# To run:
# uvicorn server:app --host localhost --port 8000
