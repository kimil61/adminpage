# 🔮 Fortune Commerce Platform

> **AI 기반 운세 콘텐츠 커머스 플랫폼**  
> FastAPI + 포인트 시스템 + 구독 모델로 구성된 완전한 운세 서비스
---

## 🌟 **프로젝트 개요**

Fortune Commerce는 **AI 기반 사주 분석**과 **행운 포인트 시스템**, **구독 모델**을 결합한 혁신적인 운세 콘텐츠 플랫폼입니다. 

사용자는 행운 포인트로 다양한 운세 상품을 구매하거나, 정기구독을 통해 할인된 가격으로 프리미엄 서비스를 이용할 수 있습니다.

### ✨ **핵심 가치 제안**

- 🎯 **개인화된 AI 분석**: 사용자별 맞춤 사주팔자 해석
- 💎 **유연한 결제 시스템**: 포인트 & 구독 하이브리드 모델
- 📊 **데이터 기반 인사이트**: 상세한 PDF 리포트 제공
- 🎁 **리워드 시스템**: 출석체크, 추천 보상, 충성도 프로그램

---

## 🚀 **주요 기능**

### 🛒 **운세 상점 시스템**
- **카테고리별 상품**: 사주, 타로, 궁합, 연간운세 등
- **난이도별 분석**: 기본/상세/프리미엄 3단계
- **행운 포인트 결제**: 현금 없이도 서비스 이용 가능
- **즉시 분석**: 구매 후 실시간 AI 분석 결과 제공

### 💎 **구독 모델**
- **Basic Plan**: 월 200 포인트 + 5% 할인
- **Premium Plan**: 월 300 포인트 + 15% 할인 + 우선지원
- **VIP Plan**: 무제한 포인트 + 25% 할인 + 독점 콘텐츠
- **자동 갱신**: 매월 자동 포인트 충전 및 혜택 적용

### 🎮 **행운 포인트 시스템**
- **충전 패키지**: 100P(1,000원) ~ 10,000P(90,000원)
- **보너스 적립**: 대용량 충전시 추가 보너스
- **유효기간 관리**: 포인트별 만료일 자동 관리
- **사용 내역**: 상세한 포인트 사용 기록 제공

### 🎯 **AI 분석 엔진**
- **GPT-4o 기반**: 최신 AI 모델로 정확한 분석
- **다층 프롬프트**: 3단계 검증 시스템
- **개인화 알고리즘**: 사용자 이력 기반 맞춤 분석
- **PDF 리포트**: 전문적인 분석 보고서 생성

### 📱 **사용자 경험**
- **직관적 인터페이스**: 모바일 우선 반응형 디자인
- **실시간 알림**: 분석 완료, 포인트 적립 등 즉시 알림
- **마이페이지**: 구매 내역, 포인트 현황, 구독 관리 통합
- **리뷰 시스템**: 실제 사용자 평가 및 추천 시스템

---

## 🏗️ **시스템 아키텍처**

### **백엔드 스택**
- **FastAPI**: 고성능 Python 웹 프레임워크
- **SQLAlchemy**: ORM 및 데이터베이스 관리
- **MySQL**: 관계형 데이터베이스
- **Celery**: 백그라운드 작업 처리
- **Redis**: 캐싱 및 세션 관리

### **프론트엔드 스택**
- **Jinja2**: 서버사이드 템플릿 엔진
- **Bootstrap 5**: 반응형 UI 프레임워크
- **Vanilla JS**: 경량화된 클라이언트 로직
- **Chart.js**: 데이터 시각화

### **인프라 & 도구**
- **Docker**: 컨테이너화 배포
- **GitHub Actions**: CI/CD 파이프라인
- **AWS S3**: 파일 스토리지
- **CloudFlare**: CDN 및 보안

---

## 📊 **데이터베이스 설계**

### **핵심 모델 구조**

```mermaid
erDiagram
    User ||--o{ UserFortunePoint : has
    User ||--o{ Subscription : has
    User ||--o{ UserPurchase : makes
    User ||--o{ UserReview : writes
    
    Product ||--o{ SajuProduct : extends
    Product ||--o{ UserPurchase : purchased
    Product ||--o{ UserReview : reviewed
    
    Subscription ||--|| User : belongs_to
    
    UserPurchase }|--|| Product : for
    UserPurchase }|--|| User : by
    
    FortuneTransaction }|--|| User : belongs_to
```

### **주요 테이블**

| 테이블 | 설명 | 핵심 필드 |
|--------|------|-----------|
| `blog_users` | 사용자 기본 정보 | username, email, is_admin |
| `user_fortune_points` | 행운 포인트 현황 | points, total_earned, total_spent |
| `subscriptions` | 구독 관리 | plan_type, status, monthly_price |
| `products` | 운세 상품 기본정보 | name, price, category, slug |
| `saju_products` | 사주 전용 상품 | analysis_type, ai_model, fortune_cost |
| `user_purchases` | 구매 기록 | purchase_type, paid_amount, access_count |
| `fortune_transactions` | 포인트 거래 내역 | type, amount, balance_after, source |

---

## ⚡ **빠른 시작 가이드**

### **1. 환경 준비**

```bash
# 저장소 클론
git clone https://github.com/your-username/fortune-commerce.git
cd fortune-commerce

# 가상환경 설정
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### **2. 환경 변수 설정**

```bash
# .env 파일 생성
cp .env.example .env
```

```env
# 데이터베이스
DATABASE_URL=mysql://user:password@localhost/website_db

# 보안
SECRET_KEY=your-super-secret-key-here
ALGORITHM=HS256

# AI 서비스
OPENAI_API_KEY=sk-your-openai-api-key

# 결제 (포트원)
PORTONE_API_KEY=your-portone-api-key
PORTONE_SECRET=your-portone-secret

# 파일 업로드
UPLOAD_FOLDER=static/uploads
MAX_CONTENT_LENGTH=16777216

# 이메일 (선택)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### **3. 데이터베이스 설정**

```bash
# MySQL 데이터베이스 생성
mysql -u root -p
CREATE DATABASE website_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;

# 테이블 생성 및 초기 데이터 설정
python setup_db.py
```

### **4. 서버 실행**

```bash
# 개발 서버 시작
python run.py

# 또는 uvicorn 직접 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### **5. 접속 확인**

| 서비스 | URL | 기본 계정 |
|--------|-----|-----------|
| 🏠 **메인 사이트** | http://localhost:8000 | - |
| 👑 **관리자 페이지** | http://localhost:8000/admin | admin / ###### |
| 🛒 **운세 상점** | http://localhost:8000/fortune/shop | - |
| 💎 **구독 관리** | http://localhost:8000/subscription | - |
| 📚 **API 문서** | http://localhost:8000/docs | - |

---

## 📁 **프로젝트 구조**

```
fortune-commerce/
├── 📱 app/                     # FastAPI 애플리케이션 코어
│   ├── 🌐 routers/            # API 라우터
│   │   ├── main.py           # 메인 페이지 라우터
│   │   ├── auth.py           # 인증 관련
│   │   ├── fortune.py        # 행운 포인트 관리
│   │   ├── shop.py           # 운세 상점
│   │   ├── subscription.py   # 구독 관리
│   │   ├── mypage.py         # 마이페이지
│   │   ├── saju.py           # 사주 분석
│   │   ├── order.py          # 주문 처리
│   │   └── admin.py          # 관리자 페이지
│   ├── 🗄️ models.py           # SQLAlchemy 모델
│   ├── 📋 forms.py            # WTForms 폼 클래스
│   ├── 🔧 utils.py            # 유틸리티 함수
│   ├── 🔌 database.py         # 데이터베이스 연결
│   ├── ⚙️ services/          # 비즈니스 로직
│   │   ├── fortune_service.py
│   │   ├── saju_service.py
│   │   ├── subscription_service.py
│   │   └── payment_service.py
│   └── 📡 main.py             # FastAPI 앱 엔트리포인트
├── 🎨 templates/              # Jinja2 템플릿
│   ├── 📄 base.html          # 기본 레이아웃
│   ├── 🏠 index.html         # 랜딩 페이지
│   ├── 🔐 auth/              # 인증 템플릿
│   ├── 🛒 fortune/           # 운세 상점 템플릿
│   ├── 💎 subscription/      # 구독 관련 템플릿
│   ├── 👤 my/                # 마이페이지 템플릿
│   ├── 📝 blog/              # 블로그 템플릿
│   ├── 👑 admin/             # 관리자 템플릿
│   └── 🔧 components/        # 재사용 컴포넌트
├── 📁 static/                 # 정적 파일
│   ├── 🎨 css/               # CSS 스타일시트
│   ├── 💻 js/                # JavaScript 파일
│   ├── 🖼️ images/            # 이미지 파일
│   └── 📎 uploads/           # 업로드 파일
├── 🧪 tests/                  # 테스트 코드
├── 📋 requirements.txt        # Python 의존성
├── ⚙️ .env.example           # 환경변수 템플릿
├── 🛠️ setup_db.py            # DB 초기화 스크립트
├── 🚀 run.py                 # 서버 실행 스크립트
├── 🐳 docker-compose.yml     # Docker 구성
└── 📖 README.md              # 이 파일
```

---

## 🎯 **비즈니스 모델**

### **수익 구조**

| 수익원 | 설명 | 예상 수익률 |
|--------|------|-------------|
| 💰 **포인트 판매** | 행운 포인트 충전 수수료 | 35% |
| 💎 **구독 수수료** | 월간 구독 서비스 | 45% |
| 🛒 **프리미엄 상품** | 고급 분석 서비스 | 15% |
| 🤝 **제휴 수수료** | 외부 파트너 연동 | 5% |

### **타겟 고객**

- 🎯 **주 타겟**: 25-45세 여성 (운세 관심층)
- 🎯 **부 타겟**: 30-50세 남성 (투자/사업 운세)
- 🎯 **틈새 타겟**: 20대 초반 (연애/진로 고민)

### **성장 전략**

1. **📱 모바일 퍼스트**: 스마트폰 최적화 우선
2. **🎁 프리미엄 전환**: 무료 체험 → 유료 전환 유도
3. **🤝 바이럴 마케팅**: 추천 보상 시스템 활용
4. **📊 데이터 기반**: 사용자 행동 분석 및 개인화

---

## 🔧 **설정 및 커스터마이징**

### **AI 모델 설정**

```python
# app/config.py
AI_MODELS = {
    "basic": {
        "model": "gpt-3.5-turbo",
        "max_tokens": 1000,
        "temperature": 0.7
    },
    "premium": {
        "model": "gpt-4o",
        "max_tokens": 2000,
        "temperature": 0.8
    }
}
```

### **포인트 시스템 설정**

```python
# app/config.py
FORTUNE_POINT_SETTINGS = {
    "welcome_bonus": 100,        # 신규 가입 보너스
    "daily_login": 10,           # 일일 출석 보너스
    "referral_reward": 50,       # 추천인 보상
    "expiry_days": 365,          # 포인트 유효기간
}

PRICING_PACKAGES = [
    {"points": 100, "price": 1000, "bonus": 0},
    {"points": 500, "price": 4500, "bonus": 50},
    {"points": 1000, "price": 8500, "bonus": 150},
    {"points": 5000, "price": 40000, "bonus": 1000},
]
```

### **구독 플랜 설정**

```python
# app/config.py
SUBSCRIPTION_PLANS = {
    "basic": {
        "name": "베이직",
        "price": 4900,
        "monthly_points": 200,
        "discount_rate": 5,
        "features": ["월 200 포인트", "5% 할인"]
    },
    "premium": {
        "name": "프리미엄", 
        "price": 9900,
        "monthly_points": 300,
        "discount_rate": 15,
        "features": ["월 300 포인트", "15% 할인", "우선 지원"]
    }
}
```

---

## 🧪 **테스트**

### **테스트 실행**

```bash
# 전체 테스트 실행
pytest

# 커버리지 포함 테스트
pytest --cov=app tests/

# 특정 모듈 테스트
pytest tests/test_fortune_service.py -v
```

### **테스트 데이터 생성**

```bash
# 개발용 테스트 데이터 생성
python create_test_data.py

# 성능 테스트용 대량 데이터 생성
python create_bulk_test_data.py --users 1000 --products 500
```

---


### **성능 최적화**

```bash
# Gunicorn으로 운영 서버 실행
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Nginx 리버스 프록시 설정
sudo nginx -t && sudo systemctl reload nginx
```

---

## 📊 **모니터링 & 분석**

### **주요 메트릭**

- 📈 **비즈니스 지표**: 매출, 구독자 수, 포인트 사용량
- 👥 **사용자 지표**: DAU/MAU, 리텐션, 전환율
- 🔧 **기술 지표**: 응답시간, 에러율, 서버 리소스

### **분석 도구**

```python
# app/analytics.py
class BusinessAnalytics:
    def get_revenue_summary(self, period='month'):
        """매출 요약 리포트"""
        pass
    
    def get_user_behavior(self, user_id):
        """사용자 행동 분석"""
        pass
    
    def get_conversion_funnel(self):
        """전환 퍼널 분석"""
        pass
```

---

## 🛡️ **보안 & 개인정보보호**

### **보안 조치**

- 🔐 **암호화**: 비밀번호 해싱 (bcrypt)
- 🛡️ **CSRF 보호**: 토큰 기반 요청 검증
- 🚦 **Rate Limiting**: API 호출 제한
- 📝 **감사 로그**: 중요 작업 기록

### **개인정보 처리**

- ✅ **GDPR 준수**: 데이터 삭제 요청 지원
- 🔒 **최소 수집**: 필요 최소한의 정보만 수집
- 📅 **자동 삭제**: 비활성 계정 자동 정리
- 🔐 **암호화 저장**: 민감 정보 암호화

---

## 🤝 **기여 가이드**

### **개발 환경 설정**

```bash
# 개발 의존성 설치
pip install -r requirements-dev.txt

# 코드 스타일 검사
black app/ tests/
flake8 app/ tests/

# 타입 힌트 검사
mypy app/
```

### **기여 프로세스**

1. 🍴 **Fork** 후 브랜치 생성
2. 🔧 **기능 개발** 및 테스트 작성
3. 📝 **커밋 메시지** 규칙 준수
4. 🔍 **코드 리뷰** 요청
5. ✅ **CI/CD** 통과 확인

### **코딩 컨벤션**

- **Python**: PEP 8 스타일 가이드 준수
- **JavaScript**: ESLint + Prettier 설정 따름
- **HTML/CSS**: BEM 방법론 적용
- **커밋**: Conventional Commits 형식 사용

---

## 📚 **API 문서**

### **주요 엔드포인트**

| 메소드 | 엔드포인트 | 설명 | 인증 |
|--------|------------|------|------|
| `GET` | `/fortune/shop` | 운세 상품 목록 | Optional |
| `POST` | `/fortune/purchase` | 상품 구매 | Required |
| `GET` | `/my/wallet` | 포인트 현황 | Required |
| `POST` | `/subscription/subscribe` | 구독 시작 | Required |
| `GET` | `/saju/analysis/{id}` | 분석 결과 조회 | Required |

### **응답 예시**

```json
{
  "status": "success",
  "data": {
    "user_points": 150,
    "product": {
      "id": 1,
      "name": "2025년 연간 운세",
      "fortune_cost": 50,
      "description": "AI 기반 상세 분석"
    },
    "analysis_result": {
      "personality": "...",
      "fortune_2025": "...",
      "lucky_keywords": ["성공", "금전", "인간관계"]
    }
  }
}
```

---

## 🆘 **문제 해결**

### **자주 발생하는 문제**

| 문제 | 원인 | 해결방법 |
|------|------|----------|
| 🚫 **데이터베이스 연결 실패** | 환경변수 설정 오류 | `.env` 파일 DATABASE_URL 확인 |
| 🔑 **OpenAI API 오류** | API 키 미설정 | `OPENAI_API_KEY` 환경변수 설정 |
| 💰 **결제 모듈 오류** | 포트원 설정 문제 | API 키 및 시크릿 재확인 |
| 📧 **이메일 발송 실패** | SMTP 설정 오류 | Gmail 앱 비밀번호 재생성 |

### **로그 확인**

```bash
# 애플리케이션 로그
tail -f logs/app.log

# 에러 로그만 필터링
grep "ERROR" logs/app.log | tail -20

# 실시간 로그 모니터링
docker-compose logs -f web
```

---

## 📄 **라이선스**

이 프로젝트는 **MIT 라이선스** 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

## 🙋‍♂️ **지원 및 문의**

- 📧 **이메일**: dev@fortune-platform.com
- 💬 **디스코드**: [Fortune Dev Community](https://discord.gg/fortune-dev)
- 🐛 **버그 리포트**: [GitHub Issues](https://github.com/your-username/fortune-commerce/issues)
- 📖 **문서**: [Technical Documentation](https://docs.fortune-platform.com)

---

## 🎉 **크레딧**

### **개발팀**

- 👨‍💻 **백엔드**: FastAPI, SQLAlchemy 아키텍처 설계
- 🎨 **프론트엔드**: Bootstrap 5, Vanilla JS 구현
- 🤖 **AI 엔지니어**: GPT 프롬프트 최적화
- 📊 **데이터 분석**: 사용자 행동 분석 시스템

### **사용 기술**

- **웹 프레임워크**: [FastAPI](https://fastapi.tiangolo.com/)
- **템플릿 엔진**: [Jinja2](https://jinja.palletsprojects.com/)
- **ORM**: [SQLAlchemy](https://www.sqlalchemy.org/)
- **UI 프레임워크**: [Bootstrap 5](https://getbootstrap.com/)
- **AI 모델**: [OpenAI GPT](https://openai.com/)

---