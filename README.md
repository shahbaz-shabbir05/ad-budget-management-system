# Ad Budget Management System

[![CI Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/your-org/your-repo/actions)  
[![Python Version](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/downloads/release/python-3120/)  
[![Coverage Status](https://img.shields.io/badge/coverage-100%25-brightgreen)](https://github.com/your-org/your-repo/actions)

---

## Overview

A robust Django + Celery backend for ad agencies to automate ad spend tracking, budget enforcement, and campaign scheduling. Designed for reliability, observability, and type safety. Built for teams managing multiple brands and campaigns with strict budget and timing requirements.

---

## Tech Stack

- **Python 3.12**
- [Django 5.x](https://www.djangoproject.com/)
- [Celery 5.x](https://docs.celeryq.dev/)
- [Redis 5.x](https://redis.io/) (broker & result backend)
- [pytest](https://docs.pytest.org/)
- [django-environ](https://django-environ.readthedocs.io/)
- [mypy](https://mypy.readthedocs.io/)

---

## Architecture Reference

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for:
- Data models
- Workflow pseudo-code
- System design assumptions

---

## Table of Contents

- [Features](#features)
- [Quickstart / Getting Started](#quickstart--getting-started)
- [Detailed Setup](#detailed-setup)
- [Configuration](#configuration)
  - [How to Create and Add the Django Secret Key](#how-to-create-and-add-the-django-secret-key)
- [Running the Project](#running-the-project)
- [Running Tests](#running-tests)
- [Logging & Observability](#logging--observability)
- [Manual Operations / Recovery Tasks](#manual-operations--recovery-tasks)
- [Redis & Celery Broker Info](#redis--celery-broker-info)
- [Folder Structure](#folder-structure)
- [Contributing](#contributing)
- [Deployment Notes](#deployment-notes)
- [License](#license)

---

## Features

- **Automatic spend tracking** for daily and monthly budgets
- **Budget enforcement**: auto-pause campaigns exceeding limits
- **Dayparting support**: control when campaigns can run
- **Periodic resets**: daily/monthly spend resets & campaign reactivation
- **Comprehensive logging** for observability and debugging
- **Type-safe code**: full static typing with mypy
- **Admin interface**: manage brands, campaigns, and schedules

---

## Quickstart / Getting Started

Clone, configure, and run the project in minutes:

```bash
# 1. Clone the repo
git clone https://github.com/your-org/ad-budget-management-system.git
cd ad-budget-management-system

# 2. Create and activate a virtual environment named 'ads-venv'
python3.12 -m venv ads-venv
source ads-venv/bin/activate  # On Windows: ads-venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment config and edit as needed
cp .env.example .env
# (Edit .env with your secrets and settings)

# 5. Run migrations and seed sample data
python manage.py migrate
python manage.py seed_data

# 6. Start services (in separate terminals or background)
celery -A ad_budget_system worker --loglevel=info
celery -A ad_budget_system beat --loglevel=info
python manage.py runserver
```

---

## Detailed Setup

### 1. Virtual Environment

Create a virtual environment named `ads-venv`:

```bash
python3.12 -m venv ads-venv
```

Activate the virtual environment:

- **On macOS/Linux:**
  ```bash
  source ads-venv/bin/activate
  ```
- **On Windows:**
  ```bash
  ads-venv\Scripts\activate
  ```

You should see `(ads-venv)` at the beginning of your command prompt when activated.

### Windows Installation Guidelines

If you are a Windows user, follow these additional steps:

- **Python & Virtual Environment:**
  - Make sure Python 3.12 is installed and added to your PATH.
  - Create the virtual environment as above:
    ```cmd
    python -m venv ads-venv
    ads-venv\Scripts\activate
    ```
- **Redis on Windows:**
  - Redis does not officially support Windows. You can:
    - Use [Memurai](https://www.memurai.com/) (Redis-compatible for Windows)
    - Or run Redis via [WSL](https://learn.microsoft.com/en-us/windows/wsl/) (Windows Subsystem for Linux)
    - Or use Docker Desktop for Windows:
      ```cmd
      docker run -p 6379:6379 redis
      ```
- **Environment Variables:**
  - Edit `.env` with Notepad or your preferred editor.
- **Command Prompt vs. PowerShell:**
  - Activation commands may differ slightly in PowerShell:
    ```powershell
    .\ads-venv\Scripts\Activate.ps1
    ```
- **General Tips:**
  - Always run commands from the project root directory.
  - Use `python` instead of `python3.12` if that's how Python is installed on your system.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your configuration
```

- Never commit your real `.env` file to version control.
- Update `.env.example` if you add new variables.

### How to Create and Add the Django Secret Key

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```
2. **Generate a new Django secret key:**
   Run this command in your terminal:
   ```bash
   python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
   ```
3. **Add the key to your `.env` file:**
   - Open `.env` in a text editor.
   - Find the line starting with `DJANGO_SECRET_KEY=`
   - Replace the value with your generated key, e.g.:
     ```env
     DJANGO_SECRET_KEY=your-generated-secret-key-here
     ```
   - Do not add quotes or spaces around the key.
4. **Save the `.env` file.**

- Never share or commit your real secret key.
- Each developer should generate their own unique secret key for local development.
- The `.env` file will be loaded automatically when you run Django or Celery commands.

### 4. Database Setup

```bash
python manage.py migrate
python manage.py seed_data  # Loads sample brands, campaigns, schedules
```

### 5. Create Superuser (optional)

```bash
python manage.py createsuperuser
```

---

## Configuration

All configuration is via environment variables in `.env`:

- `DJANGO_SECRET_KEY`: Django secret key
- `DJANGO_DEBUG`: `True` (dev) or `False` (prod)
- `DJANGO_ALLOWED_HOSTS`: Comma-separated list
- `DATABASE_URL`: e.g. `sqlite:///db.sqlite3` or `postgres://user:pass@host:port/db`
- `CELERY_BROKER_URL`: e.g. `redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND`: e.g. `redis://localhost:6379/0`
- `DEFAULT_SPEND_CHECK_INTERVAL_MINUTES`: How often (in minutes) to check/enforce budgets (default: 15 minutes)
- `DEFAULT_BUDGET_CHECK_FREQUENCY`: Default interval for budget checks (in minutes, default: 15)
- `DAILY_RESET_CRON`: Cron for daily reset (default: `0 2 * * *`)
- `MONTHLY_RESET_CRON`: Cron for monthly reset (default: `30 1 1 * *`)

See `.env.example` for all variables and sample values.

---

## Running the Project

- **Django server:**
  ```bash
  python manage.py runserver
  ```
- **Celery worker:**
  ```bash
  celery -A ad_budget_system worker --loglevel=info
  ```
- **Celery beat (scheduler):**
  ```bash
  celery -A ad_budget_system beat --loglevel=info
  ```

You can run these in separate terminals, or background them in one shell:

```bash
celery -A ad_budget_system worker --loglevel=info &
celery -A ad_budget_system beat --loglevel=info &
python manage.py runserver
```

---

## Running Tests

- **Run all tests:**
  ```bash
  pytest
  ```
- **Type checking:**
  ```bash
  mypy .
  ```
- **Test coverage:**
  ```bash
  pytest --cov=ads
  ```
- **Linting:**
  ```bash
  flake8
  black --check .
  isort --check .
  ```

---

## Logging & Observability

- **Default:** Logs to console at INFO level
- **File logging:** Optional, configure in `settings.py`
- **What’s logged:**
  - Campaign pauses/reactivations
  - Task start/finish
  - Errors with stack traces
  - Structured data: campaign IDs, spend, timestamps
- **Logger naming:** Always `logger` (lowercase), via `logging.getLogger(__name__)`

---

## Manual Operations / Recovery Tasks

### Management Commands

If Celery Beat is down or you need to trigger periodic tasks manually, you can use the following Django management commands:

- **Reset Spend:**
  - Daily:   `python manage.py reset_spend --type daily`
  - Monthly: `python manage.py reset_spend --type monthly`
- **Check Budget Enforcement:**
  - `python manage.py check_budget`
- **Enforce Dayparting:**
  - `python manage.py enforce_dayparting`

All commands are idempotent and safe to run multiple times.

---

## Redis & Celery Broker Info

- **Redis is required** for Celery to work.
- **Quick local start (Docker):**
  ```bash
  docker run -p 6379:6379 redis
  ```
- **macOS (Homebrew):**
  ```bash
  brew install redis
  brew services start redis
  ```
- **Manual:** See [Redis docs](https://redis.io/download)
- **Test connection:**
  ```bash
  redis-cli ping  # Should return: PONG
  ```
- **Default Celery config:**
  - `CELERY_BROKER_URL=redis://localhost:6379/0`
  - `CELERY_RESULT_BACKEND=redis://localhost:6379/0`

---

## Folder Structure

```
ad-budget-management-system/
├── ads/                  # Main Django app (models, services, tasks, admin, etc.)
├── ad_budget_system/     # Django project settings, celery config
├── tests/                # Test suite
├── requirements.txt      # Python dependencies
├── mypy.ini              # Static typing config
├── manage.py             # Django management script
├── .env.example          # Example environment variables
└── ...
```

---

## Contributing

- Create a feature branch: `git checkout -b feature/your-feature`
- Format code: `black .` and `isort .`
- Type check: `mypy .`
- Lint: `flake8`
- Write/maintain tests for new features
- Open a pull request with a clear description

---

## Deployment Notes

- Use **PostgreSQL** in production (not SQLite)
- Use **HTTPS** for all admin and API endpoints
- Store all secrets in environment variables
- Set up **backups** and **monitoring** for DB and Redis
- Scale Redis and Celery workers for high volume

---

## License

_This project is internal and not licensed for external use._

---



