from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
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

class TrackRequest(BaseModel):
    company: str
    role: str
    jd: str

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

def run_cv_optimizer(company: str, role: str, jd_text: str):
    temp_jd_path = Path("temp_jd.txt")
    temp_jd_path.write_text(jd_text, encoding="utf-8")
    
    try:
        logger.info(f"Triggering tracking pipeline for {company} - {role}")
        from cv_optimizer.tracker import track
        app_id = track(company, role, str(temp_jd_path))
        
        logger.info(f"Optimization success for app #{app_id}")
        os.system(f"""osascript -e 'display notification "Optimization complete for {role} at {company}!" with title "✅ CV Optimizer"'""")
        send_discord_notification(
            title="✅ CV Generated (Click to open Finder)",
            description=f"Successfully generated tailored CV for **{role}** at **{company}**.\nReady in `applications/`.",
            color=0x00FF00,
            url=f"http://localhost:8000/api/open/{app_id}"
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
    
    # We run the optimization in the background so the extension UI returns immediately
    background_tasks.add_task(run_cv_optimizer, request.company, request.role, request.jd)
    
    return {"status": "success", "message": f"Tracking initiated for {request.company} - {request.role}"}

from fastapi.responses import HTMLResponse

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
