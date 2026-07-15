from collections.abc import AsyncGenerator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Supabase usa pgbouncer en el pooler (puerto 6543, "Transaction pooler"),
# que no soporta prepared statements reutilizables. Hay que:
#   * statement_cache_size=0       -> desactiva la caché de asyncpg
#   * prepared_statement_cache_size=0 -> desactiva la caché de SQLAlchemy
#   * prepared_statement_name_func con UUID -> nombres únicos para evitar
#     colisiones entre conexiones reusadas por el pool (DuplicatePreparedStatementError)
_use_pgbouncer = "pooler.supabase" in settings.database_url
_connect_args = (
    {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    }
    if _use_pgbouncer
    else {}
)

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
