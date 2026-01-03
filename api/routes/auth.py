# ============= AUTH ROUTES =============
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from api.services.auth import (
    register_user, 
    login_user, 
    decode_jwt_token, 
    get_user_by_id,
    get_user_documents
)

router = APIRouter()


# ============= PYDANTIC MODELS =============

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    
    @validator('name')
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Nama tidak boleh kosong')
        return v.strip()
    
    @validator('password')
    def password_min_length(cls, v):
        if len(v) < 8:
            raise ValueError('Password minimal 8 karakter')
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


# ============= AUTH DEPENDENCY =============

async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Dependency untuk mendapatkan user dari JWT token
    """
    if not authorization:
        raise HTTPException(
            status_code=401, 
            detail="Token autentikasi diperlukan"
        )
    
    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401, 
            detail="Format token tidak valid. Gunakan: Bearer <token>"
        )
    
    token = parts[1]
    payload = decode_jwt_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=401, 
            detail="Token tidak valid atau sudah kadaluarsa"
        )
    
    # Get user from database
    user = get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(
            status_code=401, 
            detail="User tidak ditemukan"
        )
    
    return user


async def get_optional_user(authorization: Optional[str] = Header(None)):
    """
    Dependency untuk mendapatkan user jika ada token (opsional)
    """
    if not authorization:
        return None
    
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


# ============= ROUTES =============

@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """
    Register user baru
    """
    result, error = register_user(
        name=request.name,
        email=request.email,
        password=request.password
    )
    
    if error:
        if "sudah terdaftar" in error.lower():
            raise HTTPException(status_code=409, detail=error)
        raise HTTPException(status_code=400, detail=error)
    
    return result


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """
    Login user
    """
    result, error = login_user(
        email=request.email,
        password=request.password
    )
    
    if error:
        raise HTTPException(status_code=401, detail=error)
    
    return result


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Get current user info
    """
    return {
        "id": current_user["id"],
        "name": current_user["name"],
        "email": current_user["email"]
    }


@router.get("/documents")
async def get_my_documents(current_user: dict = Depends(get_current_user)):
    """
    Get all documents owned by current user
    """
    documents = get_user_documents(current_user["id"])
    return {"documents": documents}


@router.post("/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """
    Verify if token is valid
    """
    return {
        "valid": True,
        "user": {
            "id": current_user["id"],
            "name": current_user["name"],
            "email": current_user["email"]
        }
    }
