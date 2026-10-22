from pathlib import Path
from contextlib import asynccontextmanager
import logging
import secrets

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import router
from app.services.errors import ResourceNotFoundError
from app.api.gsc_routes import router as gsc_router, CSRF_TOKEN
from app.gsc.runtime import get_runtime
from app.gsc.errors import GSCError
from app.api.technical_routes import router as technical_router
from app.technical.urls import CrawlError


@asynccontextmanager
async def lifespan(app):
    runtime = get_runtime()
    runtime.sync.recover()
    runtime.technical.recover()
    yield
    runtime.sync.close()
    runtime.technical.close()
    get_runtime.cache_clear()


class RedactOAuthAccessLog(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) >= 3 and isinstance(record.args[2], str) and "/oauth/callback" in record.args[2]:
            args = list(record.args)
            args[2] = args[2].split("?")[0] + "?[redacted]"
            record.args = tuple(args)
        return True


logging.getLogger("uvicorn.access").addFilter(RedactOAuthAccessLog())

app = FastAPI(title="SEO Local Workspace", version="0.3.0", lifespan=lifespan, docs_url=None, redoc_url=None,
              description="Local SQLite Search Console analytics, read-only Technical SEO audits and isolated demo providers.")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
                   allow_methods=["GET", "POST", "PATCH"], allow_headers=["Accept", "Content-Type", "X-CSRF-Token"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
app.mount("/docs-assets", StaticFiles(directory=Path(__file__).parent / "static" / "swagger"), name="docs-assets")


@app.middleware("http")
async def local_security(request: Request, call_next):
    origin = request.headers.get("origin")
    allowed = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000", "http://localhost:8000"}
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if origin and origin not in allowed:
            return JSONResponse(status_code=403, content={"code": "untrusted_origin", "detail": "Origin không được phép."})
        token = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(token, CSRF_TOKEN):
            return JSONResponse(status_code=403, content={"code": "csrf_required", "detail": "Phiên ứng dụng đã thay đổi. Hãy tải lại trang rồi thử lại."})
        length = request.headers.get("content-length")
        if length is None:
            return JSONResponse(status_code=411, content={"detail": "Yêu cầu cục bộ cần Content-Length để giới hạn kích thước tải lên."})
        if length and (not length.isdigit() or int(length) > 128 * 1024):
            return JSONResponse(status_code=413, content={"detail": "Nội dung tải lên vượt quá giới hạn."})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/api/integrations"):
        response.headers["Cache-Control"] = "no-store"
    return response


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
app.include_router(gsc_router)
app.include_router(technical_router)


@app.exception_handler(CrawlError)
async def crawl_error(request: Request, exc: CrawlError):
    return JSONResponse(status_code=422, content={"code": exc.code, "detail": exc.message})


@app.exception_handler(GSCError)
async def gsc_error(request: Request, exc: GSCError):
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "detail": exc.message})
