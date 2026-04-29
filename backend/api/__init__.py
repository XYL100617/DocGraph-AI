from .upload import router as upload_router
from .analyze import router as analyze_router

routers = [
    upload_router,
    analyze_router
]