from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.routes import router
from .config import get_settings
from .spark_manager import spark_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_directories()
    logging.getLogger(__name__).info(
        "Lakehouse warehouse ready at %s", settings.warehouse_dir.resolve()
    )
    yield
    spark_manager.stop()


app = FastAPI(
    title=settings.app_name,
    description=(
        "A fully local open-lakehouse workbench: run Spark SQL against Delta Lake "
        "and Apache Iceberg tables stored on the local filesystem."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def index() -> dict:
    return {
        "app": settings.app_name,
        "version": __version__,
        "docs": "/docs",
        "api": {
            "health": f"{settings.api_prefix}/health",
            "execute_sql": f"{settings.api_prefix}/execute-sql",
            "execute_pyspark": f"{settings.api_prefix}/execute-pyspark",
            "import_file": f"{settings.api_prefix}/import-file",
            "import_database": f"{settings.api_prefix}/import-database",
            "connections": f"{settings.api_prefix}/connections",
            "tables": f"{settings.api_prefix}/tables",
            "storage_explorer": f"{settings.api_prefix}/storage-explorer",
            "workspace": f"{settings.api_prefix}/workspace",
            "notebook_execute": f"{settings.api_prefix}/notebook/execute",
            "spark_config": f"{settings.api_prefix}/spark/config",
            "spark_browse": f"{settings.api_prefix}/spark/browse",
            "spark_download": f"{settings.api_prefix}/spark/download",
        },
    }
