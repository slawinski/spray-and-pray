from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import subprocess
import os
import json as json_mod
import markdown
import re
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
templates.env.filters["markdown"] = lambda s: markdown.markdown(s, extensions=["fenced_code", "codehilite"]) if s else ""

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


@app.get("/prepare-interview/{app_id}", response_class=HTMLResponse)
async def prepare_interview_page(request: Request, app_id: int):
    from cv_optimizer import db as db_mod

    app_data = db_mod.get_application(app_id)
    if not app_data:
        raise HTTPException(status_code=404, detail="Application not found")

    return templates.TemplateResponse(
        request=request,
        name="loading.html",
        context={"params": {"action": "interview", "app_id": str(app_id)}},
    )


@app.get("/prepare-learn", response_class=HTMLResponse)
async def prepare_learn_page(
    request: Request,
    concept: str = "",
    context: str = "",
    session_id: int | None = None,
    parent_lesson_id: int | None = None,
):
    if not concept:
        raise HTTPException(status_code=400, detail="concept query parameter is required")

    return templates.TemplateResponse(
        request=request,
        name="loading.html",
        context={"params": {
            "action": "learn",
            "concept": concept,
            "context": context,
            "session_id": str(session_id) if session_id else "",
            "parent_lesson_id": str(parent_lesson_id) if parent_lesson_id else "",
        }},
    )


@app.post("/api/interview/{app_id}/start")
async def start_interview(app_id: int):
    from cv_optimizer import db as db_mod
    from cv_optimizer.interview import InterviewGenerator

    app_data = db_mod.get_application(app_id)
    if not app_data:
        raise HTTPException(status_code=404, detail="Application not found")

    existing = db_mod.get_in_progress_session(app_id)
    if existing:
        url = f"http://localhost:8000/interview/{existing['id']}"
        return {
            "session_id": existing["id"],
            "session_url": url,
            "resumed": True,
        }

    generator = InterviewGenerator()
    result = generator.generate(app_id)
    session_id = result["session_id"]
    url = f"http://localhost:8000/interview/{session_id}"

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

    for eval_item in evaluations:
        eval_item["_weakness_contexts"] = {}
        for w in eval_item.get("weaknesses", []):
            parts = [
                "Question type: interview evaluation",
                "Question: \"" + str(eval_item.get("prompt", "")) + "\"",
                "Score: " + str(eval_item.get("score", 0)) + "/100",
            ]
            if eval_item.get("feedback"):
                parts.append("Evaluator feedback: " + str(eval_item["feedback"]))
            strengths = eval_item.get("strengths", [])
            if strengths:
                parts.append("What went well: " + "; ".join(strengths))
            parts.append("Weakness to address: " + w)
            eval_item["_weakness_contexts"][w] = "\n\n".join(parts)

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


class LearnRequest(BaseModel):
    concept: str
    context: str = ""
    session_id: int | None = None
    app_id: int | None = None
    parent_lesson_id: int | None = None


@app.post("/api/learn/generate")
async def generate_lesson_endpoint(request: LearnRequest):
    from cv_optimizer.interview import generate_lesson

    if not request.concept:
        raise HTTPException(status_code=400, detail="concept is required")

    result = generate_lesson(
        request.concept,
        request.context,
        request.session_id,
        request.app_id,
        request.parent_lesson_id,
    )
    url = f"http://localhost:8000/learn/{result['lesson_id']}"
    if request.session_id:
        url += f"?session_id={request.session_id}"
    return {
        "lesson_id": result["lesson_id"],
        "url": url,
    }


@app.get("/api/learn/generate")
async def generate_lesson_from_query(
    concept: str = "",
    context: str = "",
    session_id: int | None = None,
):
    from fastapi.responses import RedirectResponse
    from cv_optimizer.interview import generate_lesson

    if not concept:
        raise HTTPException(status_code=400, detail="concept query parameter is required")

    result = generate_lesson(concept, context, session_id)
    redirect_url = f"/learn/{result['lesson_id']}"
    if session_id:
        redirect_url += f"?session_id={session_id}"
    return RedirectResponse(url=redirect_url, status_code=302)


@app.get("/learn/{lesson_id}", response_class=HTMLResponse)
async def lesson_page(request: Request, lesson_id: int, session_id: int | None = None):
    from cv_optimizer import db as db_mod

    lesson = db_mod.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    lesson_sid = lesson["session_id"]
    content = json_mod.loads(lesson["content_json"])
    sections = content.get("sections", [])
    related = content.get("related_concepts", [])
    title = content.get("title", lesson["concept"])
    difficulty = content.get("difficulty", "intermediate")
    read_time = content.get("read_time_minutes", 5)

    company = None
    role = None
    if lesson["application_id"] is not None:
        app = db_mod.get_application(lesson["application_id"])
        if app is not None:
            company = app[1]
            role = app[2]

    parent_title = None
    parent_id = lesson.get("parent_lesson_id")
    if parent_id:
        parent = db_mod.get_parent_lesson(lesson["id"])
        if parent:
            parent_title = parent["title"]
            parent_id = parent["id"]

    back_sid = session_id or lesson_sid

    return templates.TemplateResponse(
        request=request,
        name="lesson.html",
        context={
            "title": title,
            "difficulty": difficulty,
            "read_time_minutes": read_time,
            "sections": sections,
            "related_concepts": related,
            "session_id": back_sid,
            "lesson_json": json_mod.dumps(content),
            "lesson_id": lesson["id"],
            "company": company,
            "role": role,
            "app_id": lesson["application_id"],
            "parent_title": parent_title,
            "parent_id": parent_id,
        },
    )


@app.get("/learn", response_class=HTMLResponse)
async def lesson_library(request: Request, session_id: int | None = None):
    from cv_optimizer import db as db_mod

    rows = db_mod.list_lessons()
    lessons = []
    for row in rows:
        content = json_mod.loads(row["content_json"])
        company = None
        role = None
        if row["application_id"] is not None:
            app = db_mod.get_application(row["application_id"])
            if app is not None:
                company = app[1]
                role = app[2]

        parent_title = None
        if row["application_id"] is None and row.get("parent_lesson_id"):
            parent = db_mod.get_parent_lesson(row["id"])
            if parent:
                parent_title = parent["title"]

        description = content.get("description") or ""
        if not description and content.get("sections"):
            first_body = content["sections"][0].get("body", "")
            m = re.match(r"^([^.!?]+[.!?])", first_body)
            if m:
                description = m.group(1)
        lessons.append({
            "id": row["id"],
            "title": content.get("title", row["concept"]),
            "concept": row["concept"],
            "difficulty": content.get("difficulty", "intermediate"),
            "read_time": content.get("read_time_minutes", 5),
            "tags": content.get("related_concepts", [])[:4],
            "company": company,
            "role": role,
            "description": description,
            "parent_title": parent_title,
            "type": "lesson" if row["application_id"] is not None else "concept",
        })

    return templates.TemplateResponse(
        request=request,
        name="lesson_library.html",
        context={"lessons": lessons, "session_id": session_id},
    )


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

@app.get("/graph", response_class=HTMLResponse)
async def graph_page(request: Request):
    from cv_optimizer import db as db_mod

    lessons = db_mod.list_lessons()

    # ── Build lesson & concept nodes ──
    lesson_nodes = []
    concept_set = {}  # lowercase_stripped → original (keep first seen)

    for lesson in lessons:
        content = json_mod.loads(lesson["content_json"])
        title = content.get("title", lesson["concept"])
        related_concepts = content.get("related_concepts", [])
        difficulty = content.get("difficulty", "intermediate")
        read_time = content.get("read_time_minutes", 5)

        # Look up application context
        company = None
        role = None
        app_id = lesson.get("application_id")
        is_lesson = app_id is not None
        if is_lesson:
            app = db_mod.get_application(app_id)
            if app is not None:
                company = app[1]
                role = app[2]

        group = f"{company} — {role}" if company and role else ("Concepts" if not is_lesson else "Unlinked")

        lesson_nodes.append({
            "id": f"l:{lesson['id']}",
            "type": "lesson" if is_lesson else "concept",
            "label": title,
            "group": group,
            "url": f"/learn/{lesson['id']}",
            "difficulty": difficulty,
            "read_time_minutes": read_time,
        })

        for concept in related_concepts:
            key = concept.strip().lower()
            if key and key not in concept_set:
                concept_set[key] = concept

    # Build index of standalone concepts (lesson nodes of type "concept") by lowercase label
    standalone_index = {}
    for ln in lesson_nodes:
        if ln["type"] == "concept":
            standalone_index[ln["label"].strip().lower()] = ln["id"]

    concept_nodes = [
        {"id": f"c:{key}", "type": "related-concept", "label": original}
        for key, original in concept_set.items()
        if key not in standalone_index  # skip concepts that already exist as standalone nodes
    ]

    # ── Build edges ──
    edges = []
    for lesson in lessons:
        lid = f"l:{lesson['id']}"
        content = json_mod.loads(lesson["content_json"])
        for concept in content.get("related_concepts", []):
            key = concept.strip().lower()
            if key:
                # If this concept has a standalone node, point to it instead of a grey dot
                target = standalone_index.get(key, f"c:{key}")
                edges.append({"source": lid, "target": target})

    # ── Parent → child concept edges ──
    for lesson in lessons:
        parent_id = lesson.get("parent_lesson_id")
        if parent_id:
            pid = f"l:{parent_id}"
            lid = f"l:{lesson['id']}"
            edges.append({"source": pid, "target": lid, "style": "parent"})

    # ── Build hulls (groups) ──
    db_mod.init_db()
    import sqlite3
    conn = sqlite3.connect(db_mod.DB_PATH)
    conn.row_factory = sqlite3.Row
    group_rows = conn.execute(
        "SELECT DISTINCT a.company, a.role FROM applications a "
        "JOIN lessons l ON l.application_id = a.id"
    ).fetchall()
    conn.close()

    # Color palette for hulls
    PALETTE = [
        "rgba(88, 166, 255, 0.12)",
        "rgba(63, 185, 80, 0.12)",
        "rgba(210, 153, 29, 0.12)",
        "rgba(248, 81, 73, 0.12)",
        "rgba(163, 113, 247, 0.12)",
        "rgba(86, 211, 200, 0.12)",
    ]

    # Map lesson → group
    lesson_group_map = {}
    for ln in lesson_nodes:
        g = ln["group"]
        lesson_group_map.setdefault(g, []).append(ln["id"])

    hulls = []
    for i, row in enumerate(group_rows):
        group_label = f"{row['company']} — {row['role']}"
        node_ids = lesson_group_map.get(group_label, [])
        hulls.append({
            "label": group_label,
            "nodeIds": node_ids,
            "color": PALETTE[i % len(PALETTE)],
        })

    # Add hull for standalone concepts (no application linked)
    concept_ids = lesson_group_map.get("Concepts", [])
    if concept_ids:
        hulls.append({
            "label": "Concepts",
            "nodeIds": concept_ids,
            "color": "rgba(63, 185, 80, 0.10)",
        })

    return templates.TemplateResponse(
        request=request,
        name="graph.html",
        context={
            "nodes_json": json_mod.dumps(lesson_nodes + concept_nodes),
            "edges_json": json_mod.dumps(edges),
            "hulls_json": json_mod.dumps(hulls),
            "node_count": len(lesson_nodes) + len(concept_nodes),
            "edge_count": len(edges),
            "hulls": hulls,
        },
    )


# To run:
# uvicorn server:app --host localhost --port 8000
