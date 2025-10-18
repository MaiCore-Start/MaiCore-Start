from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 创建一个主应用
app = FastAPI(title="MaiBot Initiate WebUI aPI")

# 设置CORS中间件，允许所有来源的跨域请求
# 注意：在生产环境中，建议将其限制为特定的前端域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
)


# 引入我们新建的 API 路由模块
from .api import settings, instances, statistics

# 将 settings 路由包含到主应用中
app.include_router(settings.router, prefix="/api", tags=["Program Settings"])
# 将 instances 路由包含到主应用中
app.include_router(instances.router, prefix="/api", tags=["Instance Management"])
# 将 statistics 路由包含到主应用中
app.include_router(statistics.router, prefix="/api", tags=["Statistics"])

@app.get("/api")
def read_root():
    """
    根路径，用于测试API是否正常工作
    """
    return {"message": "欢迎来到 MaiCore-Initiate WebUI 后端"}