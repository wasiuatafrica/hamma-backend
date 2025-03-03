from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from pathlib import Path

from common.utils.config import settings

router = APIRouter()
security = HTTPBasic()

# Setup templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    """Validate HTTP Basic Auth credentials."""
    correct_username = secrets.compare_digest(
        credentials.username, settings.dashboard_username
    )
    correct_password = secrets.compare_digest(
        credentials.password, settings.dashboard_password
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


@router.get("/", response_class=HTMLResponse)
async def get_dashboard(
    request: Request, username: str = Depends(get_current_username)
):
    """Render the dashboard template."""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/metrics", response_class=HTMLResponse)
async def get_metrics_dashboard(
    request: Request, username: str = Depends(get_current_username)
):
    """Render the metrics dashboard template."""
    return templates.TemplateResponse("metrics.html", {"request": request})


@router.get("/error-details", response_class=HTMLResponse)
async def get_error_details_page(
    request: Request, username: str = Depends(get_current_username)
):
    """Render the error details template."""
    return templates.TemplateResponse("error_details.html", {"request": request})
