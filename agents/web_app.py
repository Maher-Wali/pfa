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
    optimize_image_prompt,
)
from services.support_plan_service import SupportPlanService
from session.users import User, UserStore


IMAGE_GENERATION_MODE_KEY = "image_generation_mode"
IMAGE_GENERATION_CONVERSATION_KEY = "image_generation_conversation_id"

settings = get_settings()
db = ConversationDB(settings.sqlite_db_path)
user_store = UserStore()
support_plan_service = SupportPlanService()

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
        "mood_baseline": user.mood_baseline,
        "goals": user.goals,
        "country": user.country,
        "job": user.job,
        "relationship_status": user.relationship_status,
        "phone_number": user.phone_number,
        "whatsapp_opt_in": user.whatsapp_opt_in,
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


def _image_generation_mode_active(request: Request, conversation_id: str) -> bool:
    return (
        bool(request.session.get(IMAGE_GENERATION_MODE_KEY))
        and request.session.get(IMAGE_GENERATION_CONVERSATION_KEY) == conversation_id
    )


def _activate_image_generation_mode(request: Request, conversation_id: str) -> None:
    request.session[IMAGE_GENERATION_MODE_KEY] = True
    request.session[IMAGE_GENERATION_CONVERSATION_KEY] = conversation_id


def _reset_image_generation_mode(request: Request) -> None:
    request.session[IMAGE_GENERATION_MODE_KEY] = False
    request.session.pop(IMAGE_GENERATION_CONVERSATION_KEY, None)


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
    phone_number: str = Form(...),
    whatsapp_opt_in: str | None = Form(None),
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
            phone_number=phone_number,
            whatsapp_opt_in=whatsapp_opt_in == "yes",
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

    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "user": user,
            "conversation": conversation,
            "messages": messages,
            "image_generation_mode": _image_generation_mode_active(
                request,
                conversation_id,
            ),
        },
    )


@app.post("/chat/{conversation_id}/image-mode")
def activate_image_mode(request: Request, conversation_id: str):
    user = require_user(request)

    if isinstance(user, RedirectResponse):
        return user

    conversation = db.get_conversation(conversation_id)

    if not conversation or conversation["user_id"] != user["id"]:
        return RedirectResponse("/choose-mode", status_code=303)

    _activate_image_generation_mode(request, conversation_id)
    return RedirectResponse(f"/chat/{conversation_id}", status_code=303)


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
    phone_number: str = Form(""),
    whatsapp_opt_in: str | None = Form(None),
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

    user_store.update_profile(
        user_id=user["id"],
        age=age_int,
        job=job.strip() or None,
        relationship_status=relationship_status.strip() or None,
    )
    try:
        user_store.update_whatsapp_settings(
            user["id"],
            phone_number=phone_number,
            whatsapp_opt_in=whatsapp_opt_in == "yes",
        )
        if whatsapp_opt_in != "yes":
            support_plan_service.disable_active_plan(user["id"])
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "profile.html",
            {"user": user, "saved": False, "error": str(exc)},
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
    rag_result = agent.compare(message)

    return templates.TemplateResponse(
        request,
        "compare.html",
        {
            "user": user,
            "result": {
                "message": message,
                "mode": mode,
                "bare": bare_answer,
                "rag": rag_result["answer"],
                "passages": rag_result["passages"],
                "critique": rag_result["critique"],
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

    if _image_generation_mode_active(request, conversation_id):
        try:
            _respond_with_generated_image(
                conversation_id=conversation_id,
                conversation=conversation,
                user_input=message,
            )
        finally:
            _reset_image_generation_mode(request)

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
