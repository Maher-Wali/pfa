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
from services.image_generation import (
    ImageGenerationError,
    ImagePromptOptimizationError,
    generate_image,
    is_image_request,
    optimize_image_prompt,
)
from session.users import User, UserStore



settings = get_settings()
db = ConversationDB()
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



def _agent_for_mode(mode: str):
    if mode == "content_creation":
        return content_agent
    if mode == "virtual_therapy":
        return therapy_agent
    raise ValueError(f"Unsupported conversation mode: {mode}")


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
        user = user_store.create_user(
            email=username,
            password=password,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": str(exc)},
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


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    user = require_user(request)

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        request,
        "profile.html",
        {"user": user, "saved": False},
    )


@app.post("/profile", response_class=HTMLResponse)
def profile_save(
    request: Request,
    age: str = Form(""),
    job: str = Form(""),
    relationship_status: str = Form(""),
):
    user = require_user(request)

    if isinstance(user, RedirectResponse):
        return user

    age_int: int | None = None
    if age.strip():
        try:
            age_int = int(age.strip())
        except ValueError:
            return templates.TemplateResponse(
                request,
                "profile.html",
                {"user": user, "saved": False, "error": "Age must be a number."},
            )

    user_store.update_extracted_fields(
        user_id=user["id"],
        age=age_int,
        job=job.strip() or None,
        relationship_status=relationship_status.strip() or None,
    )

    updated = user_store.get_by_id(user["id"])
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"user": _user_dict(updated), "saved": True},
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


def _respond_with_generated_image(
    conversation_id: str,
    conversation: dict,
    user_input: str,
) -> None:
    recent_messages = db.get_recent_messages(conversation_id, limit=12)
    db.add_message(
        conversation_id=conversation_id,
        role="user",
        content=user_input,
    )

    agent = _agent_for_mode(conversation["mode"])

    try:
        final_prompt = optimize_image_prompt(
            llm=agent.llm,
            recent_messages=recent_messages,
            user_image_request=user_input,
        )
    except ImagePromptOptimizationError as exc:
        db.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=str(exc),
            metadata={"image_generation_error": True},
        )
        return

    try:
        generated = generate_image(final_prompt)
    except ImageGenerationError as exc:
        db.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=str(exc),
            metadata={
                "image_generation_error": True,
                "image_prompt": final_prompt,
            },
        )
        return

    db.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content="Generated image",
        metadata={
            "image_data_url": generated.data_url,
            "image_prompt": generated.prompt,
            "image_model": generated.model,
        },
    )


@app.get("/debug/profile/{user_id}", response_class=HTMLResponse)
def debug_profile(request: Request, user_id: str):
    user = user_store.get_by_id(user_id)

    if not user:
        return HTMLResponse(f"<pre>No user found with id: {user_id}</pre>", status_code=404)

    import json as _json
    data = {
        "user_id": user.user_id,
        "email": user.email,
        "age": user.age,
        "goals": user.goals,
        "job": user.job,
        "relationship_status": user.relationship_status,
        "profile_complete": user.profile_complete,
        "updated_at": user.updated_at,
    }
    return HTMLResponse(f"<pre>{_json.dumps(data, indent=2)}</pre>")


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

    if conversation["mode"] == "content_creation" and is_image_request(message):
        _respond_with_generated_image(
            conversation_id=conversation_id,
            conversation=conversation,
            user_input=message,
        )
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


# ── V2 routes (new design) ────────────────────────────────────────────────────

@app.get("/v2", response_class=HTMLResponse)
def v2_home(request: Request):
    user = current_user(request)
    if user:
        return RedirectResponse("/v2/conversations", status_code=303)
    return RedirectResponse("/v2/login", status_code=303)


@app.get("/v2/login", response_class=HTMLResponse)
def v2_login_page(request: Request):
    return templates.TemplateResponse(request, "v2/login.html", {"error": None})


@app.post("/v2/login")
def v2_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = user_store.authenticate(email=username.strip(), password=password)
    if not user:
        return templates.TemplateResponse(
            request,
            "v2/login.html",
            {"error": "Invalid username or password."},
        )
    request.session["user_id"] = user.user_id
    return RedirectResponse("/v2/conversations", status_code=303)


@app.get("/v2/register", response_class=HTMLResponse)
def v2_register_page(request: Request):
    return templates.TemplateResponse(request, "v2/register.html", {"error": None})


@app.post("/v2/register")
def v2_register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    username = username.strip()
    if len(username) < 3:
        return templates.TemplateResponse(
            request,
            "v2/register.html",
            {"error": "Username must contain at least 3 characters."},
        )
    if len(password) < 6:
        return templates.TemplateResponse(
            request,
            "v2/register.html",
            {"error": "Password must contain at least 6 characters."},
        )
    try:
        user = user_store.create_user(email=username, password=password)
    except ValueError:
        return templates.TemplateResponse(
            request,
            "v2/register.html",
            {"error": "This username already exists."},
        )
    request.session["user_id"] = user.user_id
    return RedirectResponse("/v2/conversations", status_code=303)


@app.get("/v2/conversations", response_class=HTMLResponse)
def v2_conversations(request: Request, mode: str = "virtual_therapy"):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return RedirectResponse("/v2/login", status_code=303)

    if mode not in {"content_creation", "virtual_therapy"}:
        mode = "virtual_therapy"

    therapy_conversations = db.list_conversations(user_id=user["id"], mode="virtual_therapy")
    content_conversations = db.list_conversations(user_id=user["id"], mode="content_creation")

    return templates.TemplateResponse(
        request,
        "v2/conversations.html",
        {
            "user": user,
            "active_mode": mode,
            "therapy_conversations": therapy_conversations,
            "content_conversations": content_conversations,
        },
    )


@app.post("/v2/conversations/{mode}/new")
def v2_new_conversation(request: Request, mode: str):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return RedirectResponse("/v2/login", status_code=303)

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
        return RedirectResponse("/v2/conversations", status_code=303)

    return RedirectResponse(f"/v2/chat/{conversation_id}", status_code=303)


@app.get("/v2/chat/{conversation_id}", response_class=HTMLResponse)
def v2_chat_page(request: Request, conversation_id: str):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return RedirectResponse("/v2/login", status_code=303)

    conversation = db.get_conversation(conversation_id)
    if not conversation or conversation["user_id"] != user["id"]:
        return RedirectResponse("/v2/conversations", status_code=303)

    messages = db.get_messages(conversation_id)
    sidebar_conversations = db.list_conversations(user_id=user["id"], mode=conversation["mode"])

    last_debug = {}
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            last_debug = msg.get("metadata") or {}
            break

    return templates.TemplateResponse(
        request,
        "v2/chat.html",
        {
            "user": user,
            "conversation": conversation,
            "messages": messages,
            "sidebar_conversations": sidebar_conversations,
            "debug": last_debug,
        },
    )


@app.post("/v2/chat/{conversation_id}")
def v2_chat_send(
    request: Request,
    conversation_id: str,
    message: str = Form(...),
):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return RedirectResponse("/v2/login", status_code=303)

    conversation = db.get_conversation(conversation_id)
    if not conversation or conversation["user_id"] != user["id"]:
        return RedirectResponse("/v2/conversations", status_code=303)

    message = message.strip()
    if not message:
        return RedirectResponse(f"/v2/chat/{conversation_id}", status_code=303)

    if conversation["mode"] == "content_creation" and is_image_request(message):
        _respond_with_generated_image(
            conversation_id=conversation_id,
            conversation=conversation,
            user_input=message,
        )
    elif conversation["mode"] == "content_creation":
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

    return RedirectResponse(f"/v2/chat/{conversation_id}", status_code=303)


@app.get("/v2/compare", response_class=HTMLResponse)
def v2_compare_page(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return RedirectResponse("/v2/login", status_code=303)

    return templates.TemplateResponse(
        request,
        "v2/compare.html",
        {"user": user, "result": None},
    )


@app.post("/v2/compare", response_class=HTMLResponse)
def v2_compare_run(
    request: Request,
    message: str = Form(...),
    mode: str = Form(...),
):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return RedirectResponse("/v2/login", status_code=303)

    message = message.strip()
    if not message or mode not in {"content_creation", "virtual_therapy"}:
        return templates.TemplateResponse(
            request,
            "v2/compare.html",
            {"user": user, "result": None},
        )

    system = CONTENT_CREATOR_SYSTEM if mode == "content_creation" else THERAPY_AGENT_SYSTEM
    agent = content_agent if mode == "content_creation" else therapy_agent

    def _passage_text(p) -> str:
        return p["text"] if isinstance(p, dict) else str(p)

    bare_answer = invoke_text(agent.llm, system, message)
    rag_result = agent.compare(message)
    selfrag_result = agent.compare_selfrag(message)

    return templates.TemplateResponse(
        request,
        "v2/compare.html",
        {
            "user": user,
            "result": {
                "message": message,
                "mode": mode,
                "bare": bare_answer,
                "rag": rag_result["answer"],
                "passages": [_passage_text(p) for p in rag_result["passages"]],
                "critique": rag_result.get("critique", ""),
                "selfrag": selfrag_result["answer"],
                "selfrag_passages": [_passage_text(p) for p in selfrag_result["passages"]],
                "selfrag_critique": selfrag_result.get("critique", ""),
                "selfrag_state": selfrag_result.get("selfrag_state", ""),
            },
        },
    )
