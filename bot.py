# ===== IMPORT =====
from pyrogram import Client, filters, enums
import asyncio
import os
import json
from datetime import datetime
from flask import Flask
import threading

# ===== CONFIG =====
# Akun 1
API_ID1 = 27117940
API_HASH1 = "0b2ecae57fafbca7da3042a735b2774a"
SESSION_NAME1 = os.environ.get("SESSION_NAME1", "userbot_session_1")
PORT1 = 3001

# Akun 2
API_ID2 = 37683797
API_HASH2 = "e40259c3108f1a89719f9840b9f5e4c9"
SESSION_NAME2 = os.environ.get("SESSION_NAME2", "userbot_session_2")
PORT2 = 3002

BROADCAST_DELAY = 4000  # detik
BROADCAST_FILE = "shared/broadcasts.json"
STATE_FILE = "shared/state.json"
GROUPS_FILE = "shared/groups.json"

# ===== INIT PYROGRAM =====
app1 = Client(SESSION_NAME1, api_id=API_ID1, api_hash=API_HASH1)
app2 = Client(SESSION_NAME2, api_id=API_ID2, api_hash=API_HASH2)

# ===== FLASK UPTIME =====
def start_flask(port):
    web_app = Flask(__name__)
    @web_app.route("/")
    def home():
        return f"✅ Userbot aktif di port {port}!"
    web_app.run(host="0.0.0.0", port=port)

def keep_alive():
    threading.Thread(target=lambda: start_flask(PORT1), daemon=True).start()
    threading.Thread(target=lambda: start_flask(PORT2), daemon=True).start()

# ===== HELPERS =====
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

broadcasts = load_json(BROADCAST_FILE, [])
state = load_json(STATE_FILE, {"running": False})
groups = load_json(GROUPS_FILE, [])

# ===== AMBIL DAFTAR GRUP =====
async def refresh_groups(client):
    found = []
    async for dialog in client.get_dialogs():
        if dialog.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            found.append(dialog.chat.id)
    save_json(GROUPS_FILE, found)
    return found

async def send_report(client, text):
    try:
        await client.send_message("me", text)
    except Exception as e:
        print("⚠️ Gagal kirim laporan:", e)

# ===== FUNGSI BOT =====
def register_bot(client):
    @client.on_message(filters.command("savepesan") & filters.me)
    async def save_message(client, message):
        if not message.reply_to_message:
            await message.reply("⚠️ Balas ke pesan yang ingin disimpan dulu.")
            return
        data = {"chat_id": message.reply_to_message.chat.id, "message_id": message.reply_to_message.id}
        broadcasts.append(data)
        save_json(BROADCAST_FILE, broadcasts)
        await message.reply(f"✅ Pesan disimpan. Total: {len(broadcasts)}")

    @client.on_message(filters.command("listpesan") & filters.me)
    async def list_message(client, message):
        if not broadcasts:
            await message.reply("📭 Belum ada pesan tersimpan.")
            return
        text = "📋 Pesan tersimpan:\n"
        for i, b in enumerate(broadcasts):
            text += f"{i}. chat_id={b['chat_id']} msg_id={b['message_id']}\n"
        await message.reply(text)

    @client.on_message(filters.command("delpesan") & filters.me)
    async def delete_message(client, message):
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            await message.reply("Gunakan format: /delpesan <index>")
            return
        idx = int(parts[1])
        if idx < 0 or idx >= len(broadcasts):
            await message.reply("Index tidak valid.")
            return
        broadcasts.pop(idx)
        save_json(BROADCAST_FILE, broadcasts)
        await message.reply(f"✅ Pesan index {idx} dihapus.")

    @client.on_message(filters.command("cekgrup") & filters.me)
    async def check_groups(client, message):
        global groups
        groups = await refresh_groups(client)
        if not groups:
            await message.reply("❌ Tidak ada grup ditemukan.")
            return
        text = f"✅ Ditemukan {len(groups)} grup:\n"
        for g in groups[:10]:
            chat = await client.get_chat(g)
            text += f"- {chat.title} ({g})\n"
        await message.reply(text)

    # ===== BROADCAST =====
    async def do_broadcast():
        global groups
        if not groups:
            groups = await refresh_groups(client)
        if not groups:
            await send_report(client, "⚠️ Tidak ada grup ditemukan.")
            return
        total_success = total_fail = 0
        for b in broadcasts:
            for g in groups:
                try:
                    await client.forward_messages(chat_id=g, from_chat_id=b["chat_id"], message_ids=b["message_id"])
                    total_success += 1
                except Exception:
                    total_fail += 1
        waktu = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        await send_report(client, f"📣 Broadcast selesai ({waktu})\n✅ Sukses: {total_success}\n❌ Gagal: {total_fail}\n👥 Total grup: {len(groups)}")

    async def auto_broadcast():
        while state.get("running", False):
            await do_broadcast()
            await asyncio.sleep(BROADCAST_DELAY)

    @client.on_message(filters.command("startbroadcast") & filters.me)
    async def start_broadcast(client, message):
        if state.get("running", False):
            await message.reply("ℹ️ Broadcast sudah berjalan.")
            return
        state["running"] = True
        save_json(STATE_FILE, state)
        await message.reply(f"▶️ Broadcast dimulai. Mengulang tiap {BROADCAST_DELAY//60} menit.")
        asyncio.create_task(auto_broadcast())

    @client.on_message(filters.command("stopbroadcast") & filters.me)
    async def stop_broadcast(client, message):
        if not state.get("running", False):
            await message.reply("ℹ️ Broadcast sudah berhenti.")
            return
        state["running"] = False
        save_json(STATE_FILE, state)
        await message.reply("⏹ Broadcast dihentikan.")

    @client.on_message(filters.command("status") & filters.me)
    async def status(client, message):
        await message.reply(f"🔎 Status: {'ON' if state['running'] else 'OFF'}\n🗂 Pesan tersimpan: {len(broadcasts)}\n👥 Grup terdeteksi: {len(groups)}\n⏱ Delay antar siklus: {BROADCAST_DELAY//60} menit")

# Daftarkan ke kedua akun
register_bot(app1)
register_bot(app2)

# ===== RUN =====
async def main():
    await asyncio.gather(
        app1.start(),
        app2.start()
    )
    while True:
        await asyncio.sleep(60)  # tetap jalan

if __name__ == "__main__":
    print("🚀 Menjalankan 2 userbot & Flask uptime server...")
    keep_alive()
    asyncio.run(main())
