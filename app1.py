import csv
import threading
import time
from datetime import datetime
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import pytchat

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# 加入 async_mode='eventlet' 提升效能，沒有裝的話會自動降級
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- 必填設定 ---
# 請務必確認這裡是 "直播 ID" 而不是 "網址"
YOUTUBE_VIDEO_ID = "你的直播影片ID" #你的直播影片ID
CSV_FILE = 'minesweeper_log1.csv'

def letter_to_index(letter):
    index = 0
    for char in letter.upper():
        if 'A' <= char <= 'Z':
            index = index * 26 + (ord(char) - ord('A') + 1)
    return index - 1

def log_to_csv(user_id, action, coord_str, result):
    try:
        with open(CSV_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, action, coord_str, result])
    except Exception as e:
        print(f"❌ CSV 寫入失敗: {e}")

def youtube_listener():
    print(f"👀 [系統] 啟動監聽器，目標 ID: {YOUTUBE_VIDEO_ID}")
    
    try:
        chat = pytchat.create(video_id=YOUTUBE_VIDEO_ID)
        print("✅ [系統] Pytchat 連線成功！等待訊息中...")
        
        while chat.is_alive():
            try:
                for c in chat.get().sync_items():
                    msg = c.message.strip()
                    user = c.author.name
                    print(f"📩 [收到訊息] {user}: {msg}") # 這裡會印出所有聊天室內容
                    
                    cmd_type = None
                    if msg.startswith("!open"): cmd_type = "open"
                    elif msg.startswith("!flag"): cmd_type = "flag"
                    
                    if cmd_type:
                        parts = msg.split()
                        if len(parts) == 3:
                            col_letter = parts[1].upper()
                            try:
                                row_input = int(parts[2])
                                
                                col_idx = letter_to_index(col_letter)
                                row_idx = row_input - 1
                                
                                if row_idx < 0:
                                    print(f"⚠️ [無效座標] {user} 輸入了 {row_input} (小於1)")
                                    continue

                                print(f"🚀 [發送指令] 準備傳送給前端: {cmd_type} {col_letter}{row_input}")
                                
                                # 使用 socketio.emit 必須在 context 下，或直接呼叫
                                socketio.emit('game_command', {
                                    'action': cmd_type,
                                    'x': col_idx,
                                    'y': row_idx,
                                    'user': user,
                                    'coord_label': f"{col_letter}{row_input}"
                                })
                                
                            except ValueError:
                                print(f"⚠️ [格式錯誤] 無法解析數字: {parts[2]}")
            except Exception as e:
                print(f"❌ [監聽迴圈錯誤] {e}")
            
            # 稍微休息避免 CPU 飆高
            socketio.sleep(0.1) 
            
        print("🔴 [系統] 直播似乎結束了，或 Pytchat 斷線。")
        
    except Exception as e:
        print(f"❌ [致命錯誤] 無法連接 YouTube: {e}")
        print("👉 請檢查 Video ID 是否正確？直播是否正在進行中？")

@app.route('/')
def index():
    return render_template('i1.html')

@socketio.on('connect')
def test_connect():
    print('✅ [WebSocket] 前端網頁已連線')

@socketio.on('report_result')
def handle_result(data):
    print(f"📝 [前端回報] {data['user']} -> {data['result']}")
    log_to_csv(data['user'], "ACTION", data['coord'], data['result'])

if __name__ == '__main__':
    # 使用 socketio.start_background_task 取代原本的 threading
    # 這是配合 Flask-SocketIO 最穩定的寫法
    socketio.start_background_task(target=youtube_listener)
    
    print("✨ 伺服器啟動中: http://localhost:5000")
    socketio.run(app, port=5000, debug=False)


