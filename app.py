import csv
import threading
import time
from datetime import datetime
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import pytchat
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# 加入 async_mode='eventlet' 提升效能，沒有裝的話會自動降級
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- 必填設定 ---
# 請務必確認這裡是 "直播 ID" 而不是 "網址"
YOUTUBE_VIDEO_ID = input("你的直播影片ID:")
CSV_FILE = 'minesweeper_log2.csv'


def letter_to_index(letter):
    index = 0
    for char in letter.upper():
        if 'A' <= char <= 'Z':
            index = index * 26 + (ord(char) - ord('A') + 1)
    return index - 1

def parse_coordinate(full_msg):
    """
    自動判斷兩個參數中，哪一個是字母(欄)，哪一個是數字(列)
    支援格式：A 6, 6 A, A6, 6A (如果觀眾沒打空格的情況)
    從完整訊息中自動提取 字母(欄) 與 數字(列)
    支援：!open G7, !open 7G, !open G 7, !open AA10
    """
    # 移除指令頭部，只留下座標部分 (例如: G7 或 G 7)
    # 我們移除 !OPEN 或 !FLAG 後的內容
    coord_part = re.sub(r'!(OPEN|FLAG)', '', full_msg, flags=re.IGNORECASE).strip().upper()
    
    # 使用正則表達式分別抓取「連續字母」與「連續數字」
    letters = re.findall(r'[A-Z]+', coord_part)
    numbers = re.findall(r'\d+', coord_part)
    
    if letters and numbers:
        # 回傳抓到的第一個字母組與第一個數字組
        return letters[0], int(numbers[0])
    
    return None, None

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
                    # --- 新增：將所有訊息發送到聊天室視窗 ---
                    cmd_type = None
                    # 指令匹配
                    # 判斷是否為指令
                    if msg.startswith("!open") or msg.startswith("!flag"):
                        cmd_type = "open" if msg.startswith("!open") else "flag"
                        
                        # 呼叫強化的解析函式
                        col_letter, row_input = parse_coordinate(msg)
                        
                        if col_letter and row_input:
                            col_idx = letter_to_index(col_letter)
                            row_idx = row_input - 1  # 1-based 轉 0-based
                            
                            if row_idx >= 0:
                                # 發送給前端
                                socketio.emit('game_command', {
                                    'action': cmd_type,
                                    'x': col_idx,
                                    'y': row_idx,
                                    'user': user,
                                    'coord_label': f"{col_letter}{row_input}"
                                })
                                # 同步發送到右上角聊天室視窗，並標記為指令
                                socketio.emit('new_chat', {
                                    'user': user,
                                    'msg': f"[{cmd_type.upper()}] {col_letter}{row_input}",
                                    'is_cmd': True,
                                    'time': datetime.now().strftime("%H:%M")
                                })
                    else:
                        socketio.emit('new_chat', {
                            'user': user,
                            'msg': msg,
                            'time': datetime.now().strftime("%H:%M")
                        })  

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
    return render_template('index.html')

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


