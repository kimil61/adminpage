from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]

    class Config:
        from_attributes = True


class PostResponse(BaseModel):
    id: int
    title: str
    slug: str
    excerpt: Optional[str]
    featured_image: Optional[str]
    is_published: bool
    views: int
    created_at: datetime
    author: UserResponse
    category: Optional[CategoryResponse]

    class Config:
        from_attributes = True


PostResponse.model_rebuild()
