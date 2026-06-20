from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
from pathlib import Path
import logging

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

def run_cv_optimizer(company: str, role: str, jd_text: str):
    # Create a temporary file for the job description text
    temp_jd_path = Path("temp_jd.txt")
    temp_jd_path.write_text(jd_text, encoding="utf-8")
    
    try:
        logger.info(f"Triggering cv-opt track for {company} - {role}")
        # Run the cv-opt track command
        result = subprocess.run(
            ["./cv-opt", "track", company, role, "--jd", str(temp_jd_path)],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"cv-opt failed: {result.stderr}")
            os.system(f"""osascript -e 'display notification "Optimization failed for {company}." with title "❌ CV Optimizer"'""")
        else:
            logger.info(f"cv-opt success: {result.stdout}")
            os.system(f"""osascript -e 'display notification "Optimization complete for {role} at {company}!" with title "✅ CV Optimizer"'""")
            
    except Exception as e:
        logger.error(f"Error executing cv-opt: {e}")
        os.system(f"""osascript -e 'display notification "Error executing command." with title "❌ CV Optimizer"'""")
    finally:
        # Clean up temporary file
        if temp_jd_path.exists():
            temp_jd_path.unlink()

@app.post("/api/track")
async def track_application(request: TrackRequest, background_tasks: BackgroundTasks):
    if not request.company or not request.role or not request.jd:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # We run the optimization in the background so the extension UI returns immediately
    background_tasks.add_task(run_cv_optimizer, request.company, request.role, request.jd)
    
    return {"status": "success", "message": f"Tracking initiated for {request.company} - {request.role}"}

# To run:
# uvicorn server:app --host localhost --port 8000
