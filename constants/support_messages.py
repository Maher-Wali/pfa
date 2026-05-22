FORBIDDEN_SUPPORT_MESSAGE_WORDS = (
    "suicide",
    "depression",
    "self-harm",
    "kill",
    "die",
)


SUPPORT_MESSAGES = [
    "Good morning. Today's step: take three slow breaths, drink a glass of water, and place one small thing in order around you. Reply STOP any time to turn these check-ins off.",
    "Good morning. Today's step: feel both feet on the floor, name five things you can see, and choose one gentle task for the next ten minutes.",
    "Good morning. Today's step: open a window or step outside for one minute, notice the air, then return to one small thing you can do now.",
    "Good morning. Today's step: text one trusted person a simple line like, 'Could you check in with me today?'",
    "Good morning. Today's step: eat something simple if you can, even a small snack, and let that count as care for today.",
    "Good morning. Today's step: write three words about how your body feels right now. No need to explain them.",
    "Good morning. Today's step: stretch your shoulders, unclench your jaw, and take one slower breath than usual.",
    "Good morning. Today's step: tidy one tiny area, such as a cup, a pillow, or one corner of a table.",
    "Good morning. Today's step: put your phone down for two minutes and listen for three nearby sounds.",
    "Good morning. Today's step: choose one kind sentence to say to yourself, such as, 'This moment is hard, and I can take one step.'",
    "Good morning. Today's step: hold a warm drink or a cool glass, notice the temperature, and let your attention rest there for a few breaths.",
    "Good morning. Today's step: make the next task smaller than you think it needs to be. One message, one dish, one breath.",
    "Good morning. Today's step: look around and name one color you can see in three different places.",
    "Good morning. Today's step: set a five-minute timer and do only the first part of one useful task.",
    "Good morning. Today's step: place one comforting object nearby, then take a slow breath while noticing its shape or texture.",
    "Good morning. Today's step: stand up if you can, roll your shoulders, and let your hands relax open.",
    "Good morning. Today's step: write down one thing that can wait until later, so today has a little more space.",
    "Good morning. Today's step: rinse your face or hands and notice the feeling of water for ten seconds.",
    "Good morning. Today's step: choose a steady phrase for today, like, 'Just the next small step.'",
    "Good morning. Today's step: check whether you need water, food, rest, or a message from someone safe. Pick one.",
    "Good morning. Today's step: put one upcoming task where you can see it, then write the smallest first action beside it.",
    "Good morning. Today's step: take a short walk around your room or nearby space and count ten slow steps.",
    "Good morning. Today's step: breathe in for four counts, breathe out for six counts, and repeat three times if it feels okay.",
    "Good morning. Today's step: notice one thing supporting you physically, like the chair, floor, bed, or wall.",
    "Good morning. Today's step: send yourself a short note for later: 'I got through this morning by taking one small step.'",
    "Good morning. Today's step: choose one routine action and do it slowly, such as brushing teeth, washing a cup, or folding one item.",
    "Good morning. Today's step: pause before the next thing and ask, 'What would make this five percent easier?'",
    "Good morning. Today's step: list one thing you can see, one sound you can hear, and one sensation you can feel.",
    "Good morning. Today's step: prepare one small thing for tomorrow, such as clothes, a note, or a glass of water.",
    "Good morning. Today's step: thank yourself for staying with the plan. Choose one gentle action for the next hour.",
]


def validate_support_messages() -> None:
    if len(SUPPORT_MESSAGES) != 30:
        raise ValueError("SUPPORT_MESSAGES must contain exactly 30 messages.")

    for index, message in enumerate(SUPPORT_MESSAGES, start=1):
        lowered = message.lower()
        blocked = [
            word
            for word in FORBIDDEN_SUPPORT_MESSAGE_WORDS
            if word in lowered
        ]
        if blocked:
            raise ValueError(
                f"Support message {index} contains blocked words: {blocked}"
            )


validate_support_messages()
