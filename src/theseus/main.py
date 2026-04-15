from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="Theseus ERP",
        description="An open-source, AI-first ERP for small manufacturing and trade businesses.",
        version="0.1.0",
    )

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "theseus"}

    return app


app = create_app()
