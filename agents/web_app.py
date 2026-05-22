from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from agents.config import get_settings
from agents.content_agent import ContentCreationAgent
from agents.database import ConversationDB
from agents.llm import invoke_text
from agents.prompts import CONTENT_CREATOR_SYSTEM, THERAPY_AGENT_SYSTEM
from agents.therapy_agent import VirtualTherapyAgent
from session.users import User, UserStore


settings = get_settings()
db = ConversationDB(settings.sqlite_db_path)
user_store = UserStore()

content_agent = ContentCreationAgent(settings=settings, db=db)
therapy_agent = VirtualTherapyAgent(settings=settings, db=db)

app = FastAPI(title="PFA Maher Agents")

app.add_middleware(
    SessionMiddleware,
    secret_key="CHANGE_THIS_SECRET_KEY_IN_PRODUCTION",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


def _user_dict(user: User) -> dict:
    """Convert User dataclass to a dict compatible with templates and session logic."""
    return {
        "id": user.user_id,
        "username": user.email,
        "email": user.email,
        "age": user.age,
        "goals": user.goals,
        "job": user.job,
        "relationship_status": user.relationship_status,
    }


def current_user(request: Request) -> dict | None:
    user_id = request.session.get("user_id")

    if not user_id:
        return None

    user = user_store.get_by_id(user_id)
    return _user_dict(user) if user else None


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
        request,
        "register.html",
        {"error": None},
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
            request,
            "register.html",
            {"error": "Username must contain at least 3 characters."},
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Password must contain at least 6 characters."},
        )

    try:
        user = user_store.create_user(email=username, password=password)
    except ValueError:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "This username already exists."},
        )

    request.session["user_id"] = user.user_id
    return RedirectResponse("/choose-mode", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None},
    )


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = user_store.authenticate(email=username.strip(), password=password)

    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid username or password."},
        )

    request.session["user_id"] = user.user_id
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
        request,
        "choose_model.html",
        {"user": user},
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
        request,
        "conversation.html",
        {"user": user, "mode": mode, "conversations": conversations_list},
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

    last_debug = {}
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            last_debug = msg.get("metadata") or {}
            break

    return templates.TemplateResponse(
        request,
        "chat.html",
        {"user": user, "conversation": conversation, "messages": messages, "debug": last_debug},
    )


@app.get("/compare", response_class=HTMLResponse)
def compare_page(request: Request):
    user = require_user(request)

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        request,
        "compare.html",
        {"user": user, "result": None},
    )


@app.post("/compare", response_class=HTMLResponse)
def compare_run(
    request: Request,
    message: str = Form(...),
    mode: str = Form(...),
):
    user = require_user(request)

    if isinstance(user, RedirectResponse):
        return user

    message = message.strip()

    if not message or mode not in {"content_creation", "virtual_therapy"}:
        return templates.TemplateResponse(
            request,
            "compare.html",
            {"user": user, "result": None},
        )

    system = CONTENT_CREATOR_SYSTEM if mode == "content_creation" else THERAPY_AGENT_SYSTEM
    agent = content_agent if mode == "content_creation" else therapy_agent

    bare_answer = invoke_text(agent.llm, system, message)

    conv_id = agent.create_conversation(user_id=user["id"])
    rag_response = agent.respond(user_id=user["id"], user_input=message, conversation_id=conv_id)
    conv_messages = db.get_messages(conv_id)
    last_meta = next(
        (m.get("metadata") or {} for m in reversed(conv_messages) if m["role"] == "assistant"),
        {},
    )
    rag_passages = last_meta.get("rag_docs", [])

    selfrag_result = agent.compare_selfrag(message)

    return templates.TemplateResponse(
        request,
        "compare.html",
        {
            "user": user,
            "result": {
                "message": message,
                "mode": mode,
                "bare": bare_answer,
                "rag": rag_response["answer"],
                "passages": rag_passages,
                "critique": rag_response.get("critique", ""),
                "selfrag": selfrag_result["answer"],
                "selfrag_passages": selfrag_result["passages"],
                "selfrag_critique": selfrag_result["critique"],
                "selfrag_state": selfrag_result["selfrag_state"],
            },
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
