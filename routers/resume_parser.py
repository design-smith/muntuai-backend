from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import os
import requests

router = APIRouter()

security = HTTPBearer()

AFFINDA_API_KEY = os.getenv("AFFINDA_API")
AFFINDA_URL = "https://api.affinda.com/v2/resumes"

@router.post("/api/parse-resume")
async def parse_resume(file: UploadFile = File(...), credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not AFFINDA_API_KEY:
        print("[ResumeParser] Affinda API key not set in environment.")
        raise HTTPException(status_code=500, detail="Affinda API key not set in environment.")
    try:
        print(f"[ResumeParser] Received file: {file.filename}, content_type: {file.content_type}")
        contents = await file.read()
        files = {"file": (file.filename, contents, file.content_type)}
        headers = {"Authorization": f"Bearer {AFFINDA_API_KEY}"}
        response = requests.post(AFFINDA_URL, headers=headers, files=files)
        print(f"[ResumeParser] Affinda response status: {response.status_code}")
        print(f"[ResumeParser] Affinda response text: {response.text[:500]}")
        if response.status_code != 200:
            return JSONResponse(status_code=500, content={"error": response.text})
        return response.json()
    except Exception as e:
        print(f"[ResumeParser] Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Affinda parsing failed: {str(e)}") 