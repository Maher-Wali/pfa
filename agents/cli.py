from __future__ import annotations

from agents.config import get_settings
from agents.content_agent import ContentCreationAgent
from agents.database import ConversationDB
from agents.therapy_agent import VirtualTherapyAgent


def print_menu() -> None:
    print("\nChoose mode:")
    print("1. Content creation")
    print("2. Virtual therapy")
    print("3. List conversations")
    print("4. Open conversation")
    print("5. Quit")


def main() -> None:
    settings = get_settings()
    db = ConversationDB(settings.sqlite_db_path)

    content_agent = ContentCreationAgent(settings=settings, db=db)
    therapy_agent = VirtualTherapyAgent(settings=settings, db=db)

    user_id = input("User ID: ").strip() or "default_user"

    current_mode = None
    current_conversation_id = None

    while True:
        print_menu()
        choice = input("\nChoice: ").strip()

        if choice == "1":
            current_mode = "content_creation"
            current_conversation_id = content_agent.create_conversation(
                user_id=user_id,
                title="Content Creation Chat",
            )
            print(f"\nStarted content creation conversation: {current_conversation_id}")

        elif choice == "2":
            current_mode = "virtual_therapy"
            current_conversation_id = therapy_agent.create_conversation(
                user_id=user_id,
                title="Virtual Therapy Chat",
            )
            print(f"\nStarted virtual therapy conversation: {current_conversation_id}")

        elif choice == "3":
            conversations = db.list_conversations(user_id=user_id)

            if not conversations:
                print("\nNo conversations found.")
                continue

            print("\nYour conversations:")

            for conv in conversations:
                print(
                    f"- {conv['id']} | {conv['mode']} | "
                    f"{conv['title']} | safety={conv['safety_status']} | "
                    f"updated={conv['updated_at']}"
                )

        elif choice == "4":
            conversation_id = input("Conversation ID: ").strip()
            conversation = db.get_conversation(conversation_id)

            if not conversation:
                print("Conversation not found.")
                continue

            current_mode = conversation["mode"]
            current_conversation_id = conversation_id

            print(
                f"\nOpened conversation: {conversation['title']} "
                f"({conversation['mode']})"
            )

            messages = db.get_messages(conversation_id)

            for message in messages:
                print(f"\n{message['role'].upper()}: {message['content']}")

        elif choice == "5":
            break

        else:
            print("Invalid choice.")
            continue

        while current_mode and current_conversation_id:
            user_input = input("\nYou: ").strip()

            if user_input.lower() in {"/back", "back"}:
                break

            if user_input.lower() in {"/quit", "quit", "exit"}:
                return

            if current_mode == "content_creation":
                result = content_agent.respond(
                    user_id=user_id,
                    user_input=user_input,
                    conversation_id=current_conversation_id,
                )

            else:
                result = therapy_agent.respond(
                    user_id=user_id,
                    user_input=user_input,
                    conversation_id=current_conversation_id,
                )

            print("\nAssistant:")
            print(result["answer"])

            if result.get("safe_mode"):
                print("\n[SAFE MODE ACTIVE]")


if __name__ == "__main__":
    main()