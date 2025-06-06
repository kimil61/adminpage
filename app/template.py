# app/template.py
from fastapi.templating import Jinja2Templates
from app.utils import get_flashed_messages

templates = Jinja2Templates(directory="templates")

templates.env.globals.update({
    "get_flashed_messages": get_flashed_messages,
})