from fastapi import FastAPI, HTTPException
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

@app.get("/")
def read_root():
    return {"status": "online", "message": "Welcome to the Galaxy Package Registry API"}

@app.get("/packages/{package_name}")
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

@app.post("/publish")
def publish_package(req: PublishRequest):
    # TODO: Insert into Supabase
    MOCK_DB[req.package_name] = req.github_repo
    return {"status": "success", "message": f"Successfully registered {req.package_name}"}
