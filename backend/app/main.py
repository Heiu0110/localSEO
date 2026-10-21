from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.services.errors import ResourceNotFoundError

app = FastAPI(title="SEO Local Workspace", version="0.1.0", docs_url=None, redoc_url=None,
              description="Offline mock Search Console analytics. All metrics are synthetic.")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
                   allow_methods=["GET"], allow_headers=["Accept", "Content-Type"])
app.mount("/docs-assets", StaticFiles(directory=Path(__file__).parent / "static" / "swagger"), name="docs-assets")


@app.get("/docs", include_in_schema=False)
def offline_docs():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title="SEO Local Workspace · API Docs",
                              swagger_js_url="/docs-assets/swagger-ui-bundle.js",
                              swagger_css_url="/docs-assets/swagger-ui.css",
                              swagger_favicon_url="/docs-assets/favicon-32x32.png",
                              swagger_ui_parameters={"validatorUrl": None})


@app.exception_handler(ResourceNotFoundError)
async def not_found(request: Request, exc: ResourceNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc.args[0])})


app.include_router(router)
