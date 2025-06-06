from sqlalchemy.orm import Session
from app.models import Post
from app.utils import create_slug

class PostService:
    def __init__(self, db: Session):
        self.db = db

    def get_published_posts(self, page: int = 1, per_page: int = 10):
        offset = (page - 1) * per_page
        return (
            self.db.query(Post)
            .filter(Post.is_published == True)
            .order_by(Post.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

    def create_post(self, post_data: dict, author_id: int) -> Post:
        slug = self._generate_unique_slug(post_data["title"])
        post = Post(**post_data, author_id=author_id, slug=slug)
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def _generate_unique_slug(self, title: str) -> str:
        base_slug = create_slug(title)
        slug = base_slug
        counter = 1
        while self.db.query(Post).filter(Post.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug
