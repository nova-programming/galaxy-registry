from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os

app = FastAPI(title="Galaxy Package Registry", description="Official package manager registry for Nova")

# Dummy database for now until Supabase is connected
# Format: "package_name": "github_username/repo_name"
MOCK_DB = {
    "nova-http": "nova-programming/nova-http",
    "nova-math": "nova-programming/nova-math"
}

class PublishRequest(BaseModel):
    package_name: str
    github_repo: str

@app.get("/", response_class=HTMLResponse)
def read_root():
    # Attempt to load the stunning HTML template
    try:
        with open("templates/index.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Galaxy Registry Online</h1>", status_code=200)

@app.get("/api/packages/{package_name}")
def get_package(package_name: str):
    # TODO: Fetch from Supabase
    repo = MOCK_DB.get(package_name)
    if not repo:
        raise HTTPException(status_code=404, detail="Package not found")
        
    return {
        "package": package_name,
        "github_repo": repo,
        "download_url": f"https://github.com/{repo}/archive/refs/heads/main.zip"
    }

@app.post("/api/publish")
def publish_package(req: PublishRequest):
    # TODO: Insert into Supabase
    MOCK_DB[req.package_name] = req.github_repo
    return {"status": "success", "message": f"Successfully registered {req.package_name}"}
