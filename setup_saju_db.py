#!/usr/bin/env python3
"""
사주팔자 서비스용 데이터베이스 테이블 생성 스크립트
"""

from app.database import engine, SessionLocal
from app.models import Base, SajuUser, SajuFortune, SajuInterpretation, MatchReport
import csv
import os
from sqlalchemy import text

def init_saju_db():
    """사주 관련 테이블 생성"""
    print("🔄 사주팔자 테이블 생성 중...")
    
    # 모든 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    # wiki_content 테이블 수동 생성
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS wiki_content (
                id INT AUTO_INCREMENT PRIMARY KEY,
                section TEXT,
                line_number INT,
                content TEXT,
                kr_literal TEXT,
                kr_explained TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """))
        print("📄 wiki_content 테이블 확인 또는 생성 완료")

    # wiki_content.csv 로드
    wiki_csv_path = "wiki_content.csv"
    if os.path.exists(wiki_csv_path):
        print("📥 wiki_content.csv 로드 중...")
        import pandas as pd
        df = pd.read_csv(wiki_csv_path)
        df.columns = [col.strip().lower() for col in df.columns]

        if df.iloc[0]["line_number"] == "line_number":
            df = df.iloc[1:]

        # 데이터 삽입
        db = SessionLocal()
        try:
            existing_rows = db.execute(text("SELECT COUNT(*) FROM wiki_content")).scalar()
            if existing_rows == 0:
                for _, row in df.iterrows():
                    try:
                        line_number = int(row["line_number"])
                    except ValueError:
                        print(f"⚠️ line_number 변환 실패: {row['line_number']}, 해당 행 건너뜀")
                        continue
                    db.execute(
                        text("INSERT INTO wiki_content (section, line_number, content, kr_literal, kr_explained) VALUES (:section, :line_number, :content, :kr_literal, :kr_explained)"),
                        {
                            "section": row["section"],
                            "line_number": line_number,
                            "content": row["content"],
                            "kr_literal": row["kr_literal"],
                            "kr_explained": row["kr_explained"],
                        }
                    )
                db.commit()
                print(f"✅ wiki_content 데이터 {len(df)}개 삽입 완료")
            else:
                print(f"ℹ️  기존 wiki_content 데이터 {existing_rows}개 발견, 삽입 생략")
        except Exception as e:
            print(f"❌ wiki_content 삽입 오류: {e}")
            db.rollback()
        finally:
            db.close()
    else:
        print("ℹ️  wiki_content.csv 파일이 존재하지 않습니다.")
    
    # CSV에서 사주 해석 데이터 불러오기 (있는 경우)
    csv_path = "ilju_db.csv"
    if os.path.exists(csv_path):
        print("📊 사주 해석 데이터 로드 중...")
        db = SessionLocal()
        try:
            # 기존 데이터 확인
            existing_count = db.query(SajuInterpretation).count()
            
            if existing_count == 0:
                with open(csv_path, newline='', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    for row in reader:
                        if len(row) < 5:
                            continue
                        
                        row = [item.strip() for item in row]
                        if row[0].startswith('\ufeff'):
                            row[0] = row[0].replace('\ufeff', '')
                        
                        type_str, ilju, cn, kr, en = row
                        
                        interpretation = SajuInterpretation(
                            type=int(type_str),
                            ilju=ilju,
                            cn=cn,
                            kr=kr,
                            en=en
                        )
                        db.add(interpretation)
                
                db.commit()
                print(f"✅ 사주 해석 데이터 {db.query(SajuInterpretation).count()}개 로드 완료")
            else:
                print(f"ℹ️  기존 사주 해석 데이터 {existing_count}개 발견, 스킵")
                
        except Exception as e:
            print(f"❌ 데이터 로드 오류: {e}")
            db.rollback()
        finally:
            db.close()
    else:
        print("ℹ️  ilju_db.csv 파일을 찾을 수 없습니다. 나중에 수동으로 추가하세요.")
    
    print("✅ 사주팔자 데이터베이스 초기화 완료!")

if __name__ == "__main__":
    init_saju_db()