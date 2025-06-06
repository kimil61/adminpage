# 🚀 FastAPI + Jinja2 웹사이트 템플릿

완전한 기능을 갖춘 웹사이트를 빠르게 구축할 수 있는 템플릿입니다.

## ✨ 주요 기능

- **FastAPI** 백엔드로 빠른 성능
- **Jinja2** 템플릿으로 서버사이드 렌더링 (SEO 최적화)
- **Bootstrap 5** 반응형 디자인
- **관리자 페이지**로 쉬운 콘텐츠 관리
- **WYSIWYG 에디터** (TinyMCE)
- **파일 업로드** 및 이미지 최적화
- **사용자 인증** (세션 기반)
- **블로그 시스템**
- **카테고리 관리**

## 🛠️ 빠른 시작

### 1. 스크립트 실행

```bash
# 스크립트에 실행 권한 부여
chmod +x setup_website.sh

# 전체 프로젝트 구조 생성
./setup_website.sh
```

### 2. 가상환경 설정

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 3. 데이터베이스 설정

```bash
# MySQL 설치 후 데이터베이스 생성
mysql -u root -p
CREATE DATABASE website_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;

# .env 파일 수정 (MySQL 비밀번호 등)
cp .env.example .env
# DATABASE_URL을 본인의 MySQL 설정에 맞게 수정
```

### 4. 초기 데이터 설정

```bash
# 데이터베이스 테이블 생성 및 관리자 계정 생성
python setup_db.py
```

### 5. 서버 실행

```bash
# 개발 서버 시작
python run.py

# 또는
uvicorn app.main:app --reload
```

### 6. 접속 확인

- 🏠 **홈페이지**: http://localhost:8000
- 👑 **관리자**: http://localhost:8000/admin
- 📚 **API 문서**: http://localhost:8000/docs

**기본 관리자 계정**: `admin` / `admin123`

## 📁 프로젝트 구조

```
my-website/
├── app/                 # FastAPI 애플리케이션
│   ├── routers/        # 라우터 (페이지별)
│   ├── models.py       # 데이터베이스 모델
│   ├── forms.py        # WTForms 폼 클래스
│   ├── utils.py        # 유틸리티 함수
│   ├── database.py     # DB 연결 설정
│   └── main.py         # 메인 애플리케이션
├── templates/          # Jinja2 템플릿
│   ├── base.html       # 기본 레이아웃
│   ├── auth/           # 인증 페이지
│   ├── blog/           # 블로그 페이지
│   ├── admin/          # 관리자 페이지
│   └── errors/         # 에러 페이지
├── static/             # 정적 파일
│   ├── css/            # CSS 파일
│   ├── js/             # JavaScript 파일
│   └── uploads/        # 업로드 파일
├── requirements.txt    # Python 패키지 목록
├── .env               # 환경 변수
├── create_admin.py    # 관리자 계정 생성
├── setup_db.py        # DB 초기화 및 샘플 데이터
├── run.py             # 서버 실행 스크립트
└── README.md          # 이 파일
```

## 🎯 사용 방법

### 관리자 페이지 사용법

1. **로그인**: `/admin` → `admin` / `admin123`
2. **카테고리 생성**: 관리자 → 카테고리 → 새 카테고리 추가
3. **포스트 작성**: 관리자 → 새 포스트 → 제목/내용 입력 → 발행
4. **파일 관리**: 포스트 작성 시 이미지 업로드 가능

### 커스터마이징

#### 디자인 변경
```css
/* static/css/style.css에서 수정 */
:root {
    --primary-color: #007bff;    /* 메인 색상 */
    --secondary-color: #6c757d;  /* 보조 색상 */
}
```

#### 사이트 이름 변경
```html
<!-- templates/base.html에서 수정 -->
<a class="navbar-brand" href="/">Your Website Name</a>
```

#### 로고 추가
```html
<!-- templates/base.html의 <head>에 추가 -->
<link rel="icon" href="/static/favicon.ico">
```

## 🔧 기술 스택

- **Backend**: FastAPI 0.104+
- **Frontend**: Jinja2 + Bootstrap 5
- **Database**: MySQL + SQLAlchemy
- **Authentication**: Session-based
- **File Upload**: Pillow (이미지 처리)
- **Forms**: WTForms
- **Editor**: TinyMCE

## 🚀 배포

### 운영 환경 설정

```bash
# .env 파일 수정
DEBUG=False
SECRET_KEY=your-production-secret-key
DATABASE_URL=mysql+pymysql://user:password@localhost/db
```

### Gunicorn으로 실행

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker 배포

```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

## 🎨 확장 아이디어

### 추가 기능 구현
- **댓글 시스템**: 포스트에 댓글 기능 추가
- **검색 기능**: 전체 텍스트 검색
- **태그 시스템**: 포스트 태깅 및 필터링
- **갤러리**: 이미지 갤러리 페이지
- **이메일 발송**: 뉴스레터, 알림 기능
- **소셜 로그인**: Google, GitHub 연동
- **API 확장**: 모바일 앱 대비 REST API

### 성능 최적화
- **캐싱**: Redis 연동
- **CDN**: 정적 파일 CDN 사용
- **이미지 최적화**: WebP 변환, 썸네일 생성
- **데이터베이스**: 인덱스 최적화

## 🛠️ 트러블슈팅

### 자주 발생하는 문제

**MySQL 연결 오류**
```bash
pip install pymysql cryptography
```

**포트 충돌**
```bash
uvicorn app.main:app --port 8001
```

**권한 오류**
```bash
chmod 755 static/uploads
```

**패키지 설치 오류**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 📝 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능합니다.

## 🤝 기여하기

1. 이 저장소를 Fork
2. 새 기능 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 Push (`git push origin feature/amazing-feature`)
5. Pull Request 생성

## 💬 지원

- **문서**: 이 README 파일
- **예제**: `setup_db.py`에서 샘플 데이터 확인
- **문제 신고**: GitHub Issues 사용

---

**🎉 즐거운 개발 되세요!**

이 템플릿으로 개인 블로그부터 회사 홈페이지까지 다양한 웹사이트를 만들어보세요!
