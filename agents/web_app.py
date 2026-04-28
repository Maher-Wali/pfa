from __future__ import annotations

import sqlite3

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from agents.config import get_settings
from agents.content_agent import ContentCreationAgent
from agents.database import ConversationDB
from agents.therapy_agent import VirtualTherapyAgent


settings = get_settings()
db = ConversationDB(settings.sqlite_db_path)

content_agent = ContentCreationAgent(settings=settings, db=db)
therapy_agent = VirtualTherapyAgent(settings=settings, db=db)

app = FastAPI(title="PFA Maher Agents")

app.add_middleware(
    SessionMiddleware,
    secret_key="CHANGE_THIS_SECRET_KEY_IN_PRODUCTION",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


def current_user(request: Request) -> dict | None:
    user_id = request.session.get("user_id")

    if not user_id:
        return None

    return db.get_user_by_id(user_id)


def require_user(request: Request):
    user = current_user(request)

    if not user:
        return RedirectResponse("/login", status_code=303)

    return user


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = current_user(request)

    if user:
        return RedirectResponse("/choose-mode", status_code=303)

    return RedirectResponse("/login", status_code=303)


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "error": None,
        },
    )


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    username = username.strip()

    if len(username) < 3:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Username must contain at least 3 characters.",
            },
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Password must contain at least 6 characters.",
            },
        )

    try:
        user_id = db.create_user(username=username, password=password)
    except sqlite3.IntegrityError:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "This username already exists.",
            },
        )

    request.session["user_id"] = user_id
    return RedirectResponse("/choose-mode", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": None,
        },
    )


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = db.verify_user(username=username.strip(), password=password)

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid username or password.",
            },
        )

    request.session["user_id"] = user["id"]
    return RedirectResponse("/choose-mode", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/choose-mode", response_class=HTMLResponse)
def choose_mode(request: Request):
    user = require_user(request)

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        "choose_mode.html",
        {
            "request": request,
            "user": user,
        },
    )


@app.get("/conversations/{mode}", response_class=HTMLResponse)
def conversations(request: Request, mode: str):
    user = require_user(request)

    if isinstance(user, RedirectResponse):
        return user

    if mode not in {"content_creation", "virtual_therapy"}:
        return RedirectResponse("/choose-mode", status_code=303)

    conversations_list = db.list_conversations(
        user_id=user["id"],
        mode=mode,
    )

    return templates.TemplateResponse(
        "conversations.html",
        {
            "request": request,
            "user": user,
            "mode": mode,
            "conversations": conversations_list,
        },
    )


@app.post("/conversations/{mode}/new")
def new_conversation(
    request: Request,
    mode: str,
):
    user = require_user(request)

    if isinstance(user, RedirectResponse):
        return user

    if mode == "content_creation":
        conversation_id = content_agent.create_conversation(
            user_id=user["id"],
            title="Content Creation Chat",
        )

    elif mode == "virtual_therapy":
        conversation_id = therapy_agent.create_conversation(
            user_id=user["id"],
            title="Virtual Therapy Chat",
        )

    else:
        return RedirectResponse("/choose-mode", status_code=303)

    return RedirectResponse(f"/chat/{conversation_id}", status_code=303)


@app.get("/chat/{conversation_id}", response_class=HTMLResponse)
def chat_page(request: Request, conversation_id: str):
    user = require_user(request)

    if isinstance(user, RedirectResponse):
        return user

    conversation = db.get_conversation(conversation_id)

    if not conversation or conversation["user_id"] != user["id"]:
        return RedirectResponse("/choose-mode", status_code=303)

    messages = db.get_messages(conversation_id)

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "user": user,
            "conversation": conversation,
            "messages": messages,
        },
    )


@app.post("/chat/{conversation_id}")
def chat_send(
    request: Request,
    conversation_id: str,
    message: str = Form(...),
):
    user = require_user(request)

    if isinstance(user, RedirectResponse):
        return user

    conversation = db.get_conversation(conversation_id)

    if not conversation or conversation["user_id"] != user["id"]:
        return RedirectResponse("/choose-mode", status_code=303)

    message = message.strip()

    if not message:
        return RedirectResponse(f"/chat/{conversation_id}", status_code=303)

    if conversation["mode"] == "content_creation":
        content_agent.respond(
            user_id=user["id"],
            user_input=message,
            conversation_id=conversation_id,
        )

    elif conversation["mode"] == "virtual_therapy":
        therapy_agent.respond(
            user_id=user["id"],
            user_input=message,
            conversation_id=conversation_id,
        )

    return RedirectResponse(f"/chat/{conversation_id}", status_code=303)