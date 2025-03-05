from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.router import api_router
from app.services.integration import register_startup, get_app_metrics
from app.models.metrics import AppMetrics

def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    description = """
    声教助手 API - 基于AI语音合成的教学声音处理软件

    ## 功能

    * **声音样本库**: 管理声音样本，支持上传、录制与分析
    * **个性化语音讲解**: 将文本转换为自然流畅的语音，支持多种参数调整
    * **标准语言输出**: 生成标准语言发音，如普通话、英语等
    * **课件语音化**: 解析PPT课件并生成语音讲解，制作有声课件
    * **声音置换**: 替换音视频中的声音，自动生成字幕
    """

    app = FastAPI(
        title="声教助手 API",
        description=description,
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # 配置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(api_router, prefix="/api")
    
    # 添加应用指标路由
    @app.get("/api/metrics", response_model=AppMetrics, tags=["系统"])
    async def get_metrics():
        """获取系统运行指标"""
        return await get_app_metrics()
        
    # 首页
    @app.get("/", tags=["系统"])
    async def root():
        """API根路径"""
        return {
            "name": "声教助手 API",
            "description": "基于AI语音合成的教学声音处理软件API",
            "version": "1.0.0",
            "docs_url": "/api/docs"
        }
    
    # 健康检查
    @app.get("/health", tags=["系统"])
    async def health_check():
        """API健康检查"""
        return {"status": "ok", "service": "voice-teaching-assistant"}
    
    # 注册启动事件
    register_startup(app)
    
    return app