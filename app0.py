import csv
import threading
from datetime import datetime
from flask import Flask, render_template
from flask_socketio import SocketIO
import pytchat

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- 設定區 ---
YOUTUBE_VIDEO_ID = "#你的直播影片ID" #你的直播影片ID
CSV_FILE = 'minesweeper_log.csv'

def letter_to_index(letter):
    index = 0
    for char in letter.upper():
        if 'A' <= char <= 'Z':
            index = index * 26 + (ord(char) - ord('A') + 1)
    return index - 1

def log_to_csv(user_id, action, coord_str, result):
    file_exists = False
    try:
        with open(CSV_FILE, 'r') as f: file_exists = True
    except FileNotFoundError: pass

    with open(CSV_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['時間', '使用者', '動作', '座標', '結果'])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, action, coord_str, result])

def youtube_listener():
    print(f"正在監聽 YouTube ID: {YOUTUBE_VIDEO_ID}")
    try:
        chat = pytchat.create(video_id=YOUTUBE_VIDEO_ID)
        while chat.is_alive():
            for c in chat.get().sync_items():
                msg = c.message.strip()
                user = c.author.name
                
                # --- 指令解析邏輯 ---
                # 支援兩種指令: !open A 5  或  !flag A 5
                cmd_type = None
                if msg.startswith("!open"):
                    cmd_type = "open"
                elif msg.startswith("!flag"):
                    cmd_type = "flag"
                
                if cmd_type:
                    parts = msg.split()
                    if len(parts) == 3:
                        try:
                            col_letter = parts[1].upper() # 例如 A
                            row_input = int(parts[2])       # 例如 5 自1起始
                            row_idx = row_input - 1   # 轉成程式索引 自0起始 (如果 <0 要擋掉)
                            col_idx = letter_to_index(col_letter)
                            
                            # 發送指令給前端
                            socketio.emit('game_command', {
                                'action': cmd_type,
                                'x': col_idx,
                                'y': row_idx,
                                'user': user,
                                'coord_label': f"{col_letter}{row_idx}"
                            })
                            print(f"[{cmd_type.upper()}] {user}: {col_letter}{row_idx}")
                            
                        except Exception as e:
                            print(f"解析錯誤: {msg} -> {e}")
    except ValueError:
        print("直播 ID 錯誤或直播未開始")

@app.route('/')
def index():
    return render_template('index0.html')

@socketio.on('report_result')
def handle_result(data):
    # 這裡會紀錄 OPEN 結果或 FLAG 動作
    log_to_csv(data['user'], "ACTION", data['coord'], data['result'])

if __name__ == '__main__':
    listener_thread = threading.Thread(target=youtube_listener, daemon=True)
    listener_thread.start()
    socketio.run(app, port=5000, debug=False)