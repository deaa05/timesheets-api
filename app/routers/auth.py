from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import Usuario
from app.schemas import Token, UsuarioCreate, UsuarioOut

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/register", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
async def registrar_usuario(payload: UsuarioCreate, db: AsyncSession = Depends(get_db)):
    existente = await db.execute(select(Usuario).where(Usuario.email == payload.email))
    if existente.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    usuario = Usuario(
        nombre_completo=payload.nombre_completo,
        email=payload.email,
        password_hash=hash_password(payload.password),
        rol=payload.rol,
    )
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)
    return usuario


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Usuario).where(Usuario.email == form_data.username))
    usuario = result.scalar_one_or_none()
    if not usuario or not verify_password(form_data.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not usuario.activo:
        raise HTTPException(status_code=403, detail="Usuario inactivo")

    token = create_access_token(subject=str(usuario.id), rol=usuario.rol.value)
    return Token(access_token=token)


@router.get("/me", response_model=UsuarioOut)
async def obtener_perfil(current_user: Usuario = Depends(get_current_user)):
    return current_user
