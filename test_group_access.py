from pyrogram import Client

api_id = 28661564
api_hash = "177feaf3caf64cd8d89613ce7d5d3a83"

app = Client("member_extractor", api_id=api_id, api_hash=api_hash)

with app:
    # List all your groups
    print("Your groups:")
    for dialog in app.get_dialogs():
        if dialog.chat.type in ["group", "supergroup"]:
            print(f"Title: {dialog.chat.title}")
            print(f"ID: {dialog.chat.id}")
            print(f"Username: @{dialog.chat.username if dialog.chat.username else 'no username'}")
            print("---")
