# migrate_sqlite_to_mysql.py
from sqlalchemy import create_engine, text
import pandas as pd

# 1️⃣ SQLite 연결 (ctext.db 경로 설정)
sqlite_engine = create_engine("sqlite:///ctext.db")

# 2️⃣ MySQL 연결 (로그인 정보 수정)
mysql_engine = create_engine("mysql+pymysql://root:jinri52@localhost/website_db?charset=utf8mb4")

# 3️⃣ wiki_content 테이블 읽기
df = pd.read_sql("SELECT * FROM wiki_content", sqlite_engine)

# 4️⃣ 칼럼 소문자로 통일 (선택사항)
df.columns = [col.strip().lower() for col in df.columns]

# 5️⃣ MySQL에 테이블이 없으면 생성
with mysql_engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS saju_wiki_contents (
            id INT AUTO_INCREMENT PRIMARY KEY,
            section TEXT,
            line_number INT,
            content TEXT,
            kr_literal TEXT,
            kr_explained TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """))
    print("✅ MySQL saju_wiki_contents 테이블 준비 완료")

# 6️⃣ 데이터 삽입
with mysql_engine.begin() as conn:
    for _, row in df.iterrows():
        try:
            conn.execute(text("""
                INSERT INTO saju_wiki_contents (section, line_number, content, kr_literal, kr_explained)
                VALUES (:section, :line_number, :content, :kr_literal, :kr_explained)
            """), {
                "section": row["section"],
                "line_number": int(row["line_number"]),
                "content": row["content"],
                "kr_literal": row["kr_literal"],
                "kr_explained": row["kr_explained"]
            })
        except Exception as e:
            print(f"❌ 에러: {e}, row: {row.to_dict()}")