"""본문에는 필요한 필드만 받고 소유자 ID는 절대 받지 않습니다."""
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Login(Input):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class Signup(Login):
    password: SecretStr = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=50)

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        if not value.strip():
            raise ValueError('이름을 입력하세요.')
        return value.strip()


class EmailInput(Input):
    email: EmailStr


class Confirmation(EmailInput):
    token: SecretStr = Field(min_length=6, max_length=10)


class PasswordReset(Confirmation):
    password: SecretStr = Field(min_length=8, max_length=128)


class Message(BaseModel):
    message: str


class CurrentUser(BaseModel):
    id: str
    email: str | None
    name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int
    expires_at: int | None
    user: CurrentUser


class PostInput(Input):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=5000)

    @field_validator('title', 'content')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('공백만 입력할 수 없습니다.')
        return value.strip()


class PostSummary(BaseModel):
    id: UUID
    author_id: UUID
    author_name: str
    title: str
    created_at: datetime
    updated_at: datetime


class PostResponse(PostSummary):
    content: str


class PostPage(BaseModel):
    items: list[PostSummary]
    total: int | None
    limit: int
    offset: int


class RecordInput(Input):
    title: str = Field(min_length=1, max_length=80)
    province: str = Field(min_length=1, max_length=30)
    city: str = Field(min_length=1, max_length=30)
    observed_on: date
    note: str = Field(default='', max_length=500)
    favorite: bool = Field(default=False, strict=True)

    @field_validator('title')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('제목을 입력하세요.')
        return value.strip()
