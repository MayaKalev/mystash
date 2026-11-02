from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime


class ItemCreate(BaseModel):
    url: HttpUrl


class TagOut(BaseModel):
    name: str


class ItemOut(BaseModel):
    id: int
    url: str
    title: str | None
    summary: str | None
    content_type: str | None
    tags: list[TagOut]
    status: str
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None
