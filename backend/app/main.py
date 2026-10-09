"""FastAPI 应用入口

负责应用创建、中间件装配、异常处理注册与路由挂载。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.redis import close_redis, get_redis

REQUEST_COUNT = Counter(
    "knowflow_http_requests_total",
    "HTTP request count",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "knowflow_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化连接，关闭时释放资源"""
    await get_redis()  # 预热 Redis 连接
    yield
    await close_redis()


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    app = FastAPI(
        title=settings.app_name,
        description="自动生长式个人知识体系工具 API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局异常处理
    register_exception_handlers(app)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        with REQUEST_LATENCY.labels(request.method, request.url.path).time():
            response = await call_next(request)
        REQUEST_COUNT.labels(
            request.method, request.url.path, str(response.status_code)
        ).inc()
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # 路由挂载
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # 健康检查
    @app.get("/health", tags=["系统"])
    async def health():
        return {"status": "ok", "app": settings.app_name, "version": "0.1.0"}

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
