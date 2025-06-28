# app/template.py
from fastapi.templating import Jinja2Templates
from app.utils import get_flashed_messages
from app.utils.csrf import generate_csrf_token

templates = Jinja2Templates(directory="templates")

templates.env.globals.update({
    "get_flashed_messages": get_flashed_messages,
    "generate_csrf_token": generate_csrf_token,
})