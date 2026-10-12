
from fastapi import FastAPI
from routes.essays import router as essays_router
from routes.chat import router as chat_router
from routes.users import router as users_router
from routes.messages import router as messages_router

app = FastAPI(
    title="Lenny Growth Assistant",
    description="AI-powered product and growth assistant",
    version="0.1.0",
)

# Register API routers
app.include_router(users_router)
app.include_router(chat_router)
app.include_router(messages_router)

app.include_router(essays_router)
@app.get("/")
def root():
    return {"message": "Lenny Growth Assistant API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
