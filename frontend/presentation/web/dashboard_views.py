from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import RedirectResponse

from presentation.container import container, templates
from presentation.middlewares.auth import get_current_user, login_required

dashboard_router = APIRouter()


@dashboard_router.get("/", name="dashboard.index")
async def index(request: Request):
    if get_current_user(request) is not None:
        return RedirectResponse(url=request.url_for("dashboard.dashboard_page"), status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url=request.url_for("auth.login_page"), status_code=status.HTTP_303_SEE_OTHER)


@dashboard_router.get("/dashboard", name="dashboard.dashboard_page")
async def dashboard_page(request: Request, user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
        
    return container.render_template(
        request,
        "dashboard.html",
        {
            "page": "dashboard",
            "stats": container.dashboard_use_cases.get_dashboard_stats(),
        }
    )



@dashboard_router.get("/api/dashboard")
async def api_dashboard(user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    return {"ok": True, "stats": container.dashboard_use_cases.get_dashboard_stats()}
