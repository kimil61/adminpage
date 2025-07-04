# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Application
```bash
# Start development server
python run.py

# Alternative - direct uvicorn command
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Database Management
```bash
# Initialize database tables and sample data
python setup_db.py

# Reset database (recreate all tables)
python setup_db.py --reset
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_order_api.py

# Run with coverage
pytest --cov=app tests/
```

### Background Tasks
```bash
# Start Celery worker (for background tasks)
python start_celery.py

# Start Celery worker with specific queue
celery -A app.celery_app worker --loglevel=info
```

## Architecture Overview

This is a **Fortune Commerce Platform** - an AI-powered astrology and fortune-telling e-commerce system built with FastAPI and Korean fortune-telling (Saju) analysis capabilities.

### Core System Components

1. **FastAPI Application** (`app/main.py`)
   - Main FastAPI app with session middleware
   - Jinja2 templates for server-side rendering
   - Multiple routers for different features

2. **Database Models** (`app/models.py`)
   - Complex e-commerce system with users, products, orders, subscriptions
   - Fortune point system (행운 포인트) for in-app currency
   - Saju analysis results storage
   - Subscription management with different tiers

3. **Router Architecture** (`app/routers/`)
   - `auth.py` - Authentication and user management
   - `saju.py` - Korean fortune-telling analysis
   - `fortune.py` - Fortune points management
   - `shop.py` - Product catalog and purchasing
   - `cart.py` - Shopping cart functionality
   - `mypage.py` - User profile and order history
   - `admin.py` - Admin dashboard
   - `order.py` - Order processing and payment

4. **Services Layer** (`app/services/`)
   - Business logic separated from routers
   - AI-powered fortune analysis
   - Payment processing
   - Cache management

### Key Features

- **AI Fortune Analysis**: OpenAI GPT-4 integration for Saju (Korean astrology) analysis
- **Fortune Points System**: Virtual currency for purchasing analyses
- **Subscription Plans**: Monthly subscription tiers with discounts
- **PDF Report Generation**: Automated report creation using multiple libraries
- **Celery Background Tasks**: Async processing for heavy operations
- **Admin Dashboard**: Complete administrative interface

### Database Schema

The system uses MySQL with SQLAlchemy ORM. Key tables include:
- `blog_users` - User accounts with admin flags
- `user_fortune_points` - Virtual currency management
- `products` & `saju_products` - Product catalog
- `user_purchases` - Purchase history
- `subscriptions` - Subscription management
- `fortune_transactions` - Point transaction history

### AI Integration

The system integrates with OpenAI's API for Korean fortune-telling analysis:
- Uses GPT-4 for detailed Saju analysis
- Multiple prompt versions for different analysis types
- Generates comprehensive PDF reports
- Handles Korean language and cultural context

### Payment Integration

- **KakaoPay Integration**: Korean payment gateway
- **Fortune Points**: Virtual currency system
- **Subscription Management**: Recurring billing
- **Order Processing**: Complete e-commerce workflow

## Development Guidelines

### When Working with Database Models
- Always use `app.database.get_db()` dependency for database sessions
- New models should inherit from `Base` in `app.models.py`
- Run `python setup_db.py` after model changes

### When Working with AI Features
- Korean fortune-telling prompts are in markdown files (e.g., `sajupalja_prompt_v13_ok.md`)
- Use the `saju_service.py` for AI analysis logic
- OpenAI API key must be set in environment variables

### When Working with Frontend
- Templates use Jinja2 in `templates/` directory
- Static files served from `static/` directory
- Bootstrap 5 is used for UI components

### Environment Variables Required
```bash
DATABASE_URL=mysql://user:password@localhost/website_db
SECRET_KEY=your-secret-key
OPENAI_API_KEY=your-openai-key
DEBUG=True
```

### Testing Guidelines
- Test files are in `tests/` directory
- Use `pytest` for running tests
- Database tests use `conftest.py` for fixtures
- API tests use `httpx` for HTTP requests

## File Structure Notes

- `app/` - Main application code
- `templates/` - Jinja2 HTML templates organized by feature
- `static/` - CSS, JS, images, and user uploads
- `tests/` - Test suite
- `*.db` files - SQLite databases for development
- `migration_*.py` - Database migration scripts
- `*_prompt_*.md` - AI prompt templates for fortune analysis