import os
import sys
import re
import json
from datetime import datetime, timezone, timedelta
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

TZ = timezone(timedelta(hours=7))
WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]

STATE_FILE = "seen_codes.json"

WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if not WEBHOOK and os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DISCORD_WEBHOOK="):
                WEBHOOK = line.split("=", 1)[1].strip().strip('"').strip("'")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_cellphones():
    codes = {}
    try:
        r = requests.get("https://cellphones.com.vn/sforum/code-play-together", headers=HEADERS, timeout=12)
        if r.status_code == 200:
            tables = re.findall(r'<table.*?>(.*?)</table>', r.text, re.DOTALL)
            for t in tables:
                rows = re.findall(r'<tr.*?>(.*?)</tr>', t, re.DOTALL)
                for row in rows:
                    cols = [re.sub(r'<.*?>', '', c).strip() for c in re.findall(r'<td.*?>(.*?)</td>', row, re.DOTALL)]
                    if len(cols) >= 3:
                        code, reward, status = cols[0], cols[1], cols[2]
                        if code and code.lower() != "code" and ("mới" in status.lower() or "còn" in status.lower()):
                            c_clean = re.sub(r'[^A-Za-z0-9_]', '', code).strip().upper()
                            if len(c_clean) >= 4 and c_clean not in codes:
                                codes[c_clean] = {
                                    "code": c_clean,
                                    "reward": reward if reward else "Quà tặng ngẫu nhiên",
                                    "status": status if status else "Mới nhất",
                                    "source": "CellphoneS"
                                }
    except Exception as e:
        print(f"[!] Lỗi cào CellphoneS: {e}")
    return codes

def fetch_hoangha():
    codes = {}
    try:
        r = requests.get("https://hoanghamobile.com/tin-tuc/code-play-together", headers=HEADERS, timeout=12)
        if r.status_code == 200:
            tables = re.findall(r'<table.*?>(.*?)</table>', r.text, re.DOTALL)
            for t in tables:
                rows = re.findall(r'<tr.*?>(.*?)</tr>', t, re.DOTALL)
                for row in rows:
                    cols = [re.sub(r'<.*?>', '', c).strip() for c in re.findall(r'<td.*?>(.*?)</td>', row, re.DOTALL)]
                    if len(cols) >= 3:
                        col0, col1, col2 = cols[0], cols[1], cols[2]
                        if ("mới" in col2.lower() or "còn" in col2.lower()) and col0.lower() != "code":
                            c_clean = re.sub(r'[^A-Za-z0-9_]', '', col0).strip().upper()
                            if len(c_clean) >= 4 and c_clean not in codes:
                                codes[c_clean] = {
                                    "code": c_clean,
                                    "reward": col1 if col1 else "Quà tặng ngẫu nhiên",
                                    "status": col2 if col2 else "Mới nhất",
                                    "source": "HoangHaMobile"
                                }
                        elif ("mới" in col0.lower() or "còn" in col0.lower()) and col1.lower() != "code":
                            c_clean = re.sub(r'[^A-Za-z0-9_]', '', col1).strip().upper()
                            if len(c_clean) >= 4 and c_clean not in codes:
                                codes[c_clean] = {
                                    "code": c_clean,
                                    "reward": col2 if col2 else "Quà tặng ngẫu nhiên",
                                    "status": col0 if col0 else "Mới nhất",
                                    "source": "HoangHaMobile"
                                }
    except Exception as e:
        print(f"[!] Lỗi cào HoangHaMobile: {e}")
    return codes

def fetch_all_codes():
    all_codes = {}
    # Ưu tiên gộp từ cả 2 nguồn lớn
    c1 = fetch_cellphones()
    c2 = fetch_hoangha()
    all_codes.update(c2)
    all_codes.update(c1)
    return all_codes

def load_seen():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
                elif isinstance(data, dict):
                    return set(data.get("seen", []))
        except Exception as e:
            print(f"[!] Lỗi đọc state: {e}")
    return set()

def save_seen(seen_set):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(seen_set)), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] Lỗi lưu state: {e}")

def send_discord(content, embeds):
    if not WEBHOOK:
        print("[!] Lỗi: Chưa cấu hình DISCORD_WEBHOOK!")
        return False
    payload = {"content": content, "embeds": embeds}
    r = requests.post(WEBHOOK, json=payload, timeout=20)
    r.raise_for_status()
    print("[+] Đã gửi thành công vào Discord!")
    return True

def create_code_embed(code_info, now):
    code = code_info["code"]
    raw_reward = code_info.get("reward", "").strip()
    raw_status = code_info.get("status", "").strip()
    
    # Chuẩn hóa phần thưởng chi tiết
    if not raw_reward or raw_reward.lower() in ("quà miễn phí", "quà ngẫu nhiên", "quà"):
        reward_display = "Kim cương, Tiền sao, Trang bị hoặc Hộp quà bí mật *(Mở hộp thư in-game để nhận)*"
    else:
        reward_display = f"**{raw_reward}** *(Gửi vào Hộp thư in-game)*"
        
    # Chuẩn hóa thời hạn sử dụng
    date_match = re.search(r'\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?', raw_status)
    if date_match:
        expire_display = f"Hết hạn vào ngày **{date_match.group(0)}**"
    elif "hết hạn" in raw_status.lower():
        expire_display = f"Theo thông báo sự kiện: **{raw_status}**"
    else:
        expire_display = "Thường kéo dài từ **24h – 48h** hoặc **giới hạn số lượt nhập** ➔ *Nhập ngay kẻo hết lượt!*"
    
    embed = {
        "title": f"🎮 MÃ QUÀ TẶNG: {code}",
        "description": (
            f"🔑 **MÃ CODE:** `{code}` *(Chạm hoặc click vào mã để sao chép)*\n\n"
            f"🎁 **Phần thưởng:** {reward_display}\n"
            f"⏳ **Hạn sử dụng:** {expire_display}\n\n"
            "──────────────────────────────────────\n"
            "📱 **HƯỚNG DẪN ĐỔI QUÀ:**\n"
            "• **Android:** Mở Game ➔ Điện thoại ➔ Cài đặt ➔ Nhập Coupon.\n"
            "• **iOS (iPhone/iPad) & PC:** Nhập trực tiếp qua liên kết web bên dưới."
        ),
        "color": 0xF1C40F, # Vàng hoàng kim Play Together
        "fields": [
            {"name": "🔗 Cổng Đổi Code VNG Chính Thức", "value": "[👉 Bấm vào đây để nhập Code VNG](http://giftcode.vnggames.com/vn/redeem)", "inline": False},
            {"name": "🌐 Cổng Quốc Tế (HAEGIN)", "value": "[👉 Bấm vào đây để nhập Code Quốc Tế](http://haegin.kr/playtogether/coupon/english.html)", "inline": False}
        ],
        "footer": {"text": "Play Together Giftcode Tracker 24/7 • Tự động gửi qua Webhook"},
        "timestamp": now.isoformat()
    }
    return embed

def main(mode="check"):
    now = datetime.now(TZ)
    thu = WEEKDAYS[now.weekday()]
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%H:%M")
    ts = int(now.timestamp())
    
    print(f"[*] Bắt đầu phiên quét Giftcode Play Together [{mode}] lúc {time_str} ({thu}, {date_str})...")
    
    active_codes = fetch_all_codes()
    print(f"[*] Tìm thấy {len(active_codes)} mã code đang hoạt động trên hệ thống.")
    
    seen = load_seen()
    
    if mode == "test":
        # Chế độ test: gửi thử nghiệm mã code mới nhất
        if active_codes:
            sample_code = list(active_codes.values())[0]
            content = (
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎁 **THỬ NGHIỆM HỆ THỐNG SĂN GIFTCODE PLAY TOGETHER**\n"
                f"⏰ *Kiểm tra lúc: {time_str} ({thu}, {date_str})* • <t:{ts}:R>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            embed = create_code_embed(sample_code, now)
            send_discord(content, [embed])
        else:
            print("[!] Không tìm thấy mã code nào để test.")
        return

    if mode == "init":
        # Khởi tạo danh sách code đã biết để không bắn tin cũ hàng loạt
        seen.update(active_codes.keys())
        save_seen(seen)
        print(f"[+] Đã khởi tạo {len(seen)} mã code cũ vào danh sách đã biết.")
        return

    # Chế độ check: tìm code mới chưa từng gửi
    new_codes = [c for c in active_codes.values() if c["code"] not in seen]
    
    if not seen and new_codes:
        # Nếu là lần đầu tiên chạy mà chưa có file seen:
        # Khởi tạo toàn bộ code hiện tại vào seen để không spam, chỉ gửi mã mới nhất làm mẫu
        seen.update(active_codes.keys())
        save_seen(seen)
        print(f"[+] Lần đầu chạy: Đã lưu {len(seen)} mã code vào danh sách theo dõi. Hệ thống sẽ báo khi có mã MỚI.")
        return

    if new_codes:
        print(f"[!] PHÁT HIỆN {len(new_codes)} MÃ CODE MỚI TINH!")
        # Giới hạn tối đa 5 mã/lần gửi để không spam Discord
        embeds = [create_code_embed(c, now) for c in new_codes[:5]]
        
        content = (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎁 **PHÁT HIỆN {len(new_codes)} MÃ GIFTCODE PLAY TOGETHER MỚI!**\n"
            f"⏰ *Cập nhật lúc: {time_str} ({thu}, {date_str})* • <t:{ts}:R>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        send_discord(content, embeds)
        
        # Cập nhật state
        for c in new_codes:
            seen.add(c["code"])
        save_seen(seen)
    else:
        print(f"[*] Không có mã code mới nào. Toàn bộ {len(seen)} mã đều đã được lưu vết. Giữ im lặng.")

if __name__ == "__main__":
    run_mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    main(run_mode)
