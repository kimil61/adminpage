from app.database import SessionLocal, engine
from app.models import Base, User
from app.utils import hash_password

def create_admin():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            print("❌ 관리자 계정이 이미 존재합니다.")
            return
        
        admin_user = User(
            username="admin",
            email="admin@example.com",
            password=hash_password("admin123"),
            is_admin=True
        )
        
        db.add(admin_user)
        db.commit()
        
        print("✅ 관리자 계정이 생성되었습니다!")
        print("🔐 사용자명: admin")
        print("⚠️  로그인 후 반드시 비밀번호를 변경하세요!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
