from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.upload import router as upload_router
from api.analyze import router as analyze_router

app = FastAPI(
    title="多模态AI信息解析系统"
)

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(upload_router)
app.include_router(analyze_router)


@app.get("/")
def root():
    return {
        "message": "Backend Running Successfully"
    }