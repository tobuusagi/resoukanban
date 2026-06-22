import os
import json
import requests
import calendar
import re
import math
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from zhdate import ZhDate

# =====================================================================
# 🌟 第一部分：用户自定义区
# =====================================================================

# 1. 控制推送哪几页？
ENABLED_PAGES = "1,2,3,4"

# 2. 热搜源设置
HOTLIST_SOURCE = "bilibili"


# =====================================================================
# 🔒 第二部分：核心密钥区（请在 GitHub Secrets 里配置） 🔒
# =====================================================================
API_KEY = os.environ.get("ZECTRIX_API_KEY")
AMAP_KEY = os.environ.get("AMAP_WEATHER_KEY")

# 🌟 HA 配置
HA_URL = os.environ.get("HA_URL", "").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")

# 🌟 多设备配置
def get_device_configs():
    """从环境变量读取设备配置，支持 HOME_ 和 OFFICE_ 前缀"""
    configs = []
    
    # 家
    home_mac = os.environ.get("HOME_MAC", "")
    if home_mac:
        configs.append({
            "mac": home_mac.strip(),
            "city": os.environ.get("HOME_CITY_ADCODE", "320402"),
            "location": os.environ.get("HOME_WTTR_LOCATION", "Tianning,Changzhou"),
            "temp_sensor": os.environ.get("HOME_HA_TEMP_SENSOR", ""),
            "humid_sensor": os.environ.get("HOME_HA_HUMID_SENSOR", ""),
            "name": "新北区"
        })
    
    # 办公室
    office_mac = os.environ.get("OFFICE_MAC", "")
    if office_mac:
        configs.append({
            "mac": office_mac.strip(),
            "city": os.environ.get("OFFICE_CITY_ADCODE", ""),
            "location": os.environ.get("OFFICE_WTTR_LOCATION", ""),
            "temp_sensor": os.environ.get("OFFICE_HA_TEMP_SENSOR", ""),
            "humid_sensor": os.environ.get("OFFICE_HA_HUMID_SENSOR", ""),
            "name": "天宁区"
        })
    
    # 兼容旧版：如果没有 HOME_/OFFICE_ 配置，使用原来的 ZECTRIX_MAC
    if not configs:
        env_mac = os.environ.get("ZECTRIX_MAC", "")
        city = os.environ.get("CITY_ADCODE", "320402")
        location = os.environ.get("WTTR_LOCATION", "Tianning,Changzhou")
        temp_sensor = os.environ.get("HA_TEMP_SENSOR", "")
        humid_sensor = os.environ.get("HA_HUMID_SENSOR", "")
        
        raw_mac_list = env_mac.split(',')
        for mac in raw_mac_list:
            mac = mac.strip()
            if mac:
                configs.append({
                    "mac": mac,
                    "city": city,
                    "location": location,
                    "temp_sensor": temp_sensor,
                    "humid_sensor": humid_sensor,
                    "name": "设备"
                })
    
    return configs

DEVICE_CONFIGS = get_device_configs()


# =====================================================================
# ⚙️ 第三部分：底层运行逻辑
# =====================================================================

# --- 字体设置 ---
FONT_PATH = "font.ttf"
WEATHER_FONT_PATH = "font_weather_icon.ttf"

try:
    font_huge = ImageFont.truetype(FONT_PATH, 65)
    font_title = ImageFont.truetype(FONT_PATH, 24)
    font_item = ImageFont.truetype(FONT_PATH, 18)
    font_small = ImageFont.truetype(FONT_PATH, 14)
    font_tiny = ImageFont.truetype(FONT_PATH, 11)
    font_48 = ImageFont.truetype(FONT_PATH, 48)
    font_36 = ImageFont.truetype(FONT_PATH, 36)
    
    font_weather_icon_large = ImageFont.truetype(WEATHER_FONT_PATH, 36)
    font_weather_icon_small = ImageFont.truetype(WEATHER_FONT_PATH, 18)
except Exception as e:
    print(f"❌ 错误: 字体文件加载失败。错误详情: {e}")
    exit(1)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# --- 工具函数 ---
def get_wrapped_lines(text, max_chars=18):
    lines = []
    while text:
        lines.append(text[:max_chars])
        text = text[max_chars:]
    return lines

def get_clothing_advice(feel_temp_str):
    """根据体感温度给出穿衣建议"""
    try:
        t = float(str(feel_temp_str).replace("°C", "").replace("°", "").strip())
        if t >= 35:
            return "极热，尽量待在室内，穿透气防晒衣物。"
        elif t >= 32:
            return "炎热，穿薄短袖短裤，注意防晒补水。"
        elif t >= 28:
            return "偏热，穿短袖短裤即可。"
        elif t >= 24:
            return "舒适，穿T恤配单裤。"
        elif t >= 20:
            return "微凉，穿长袖衬衫或薄卫衣。"
        elif t >= 16:
            return "偏凉，穿长袖加薄外套。"
        elif t >= 12:
            return "凉，穿风衣或夹克。"
        elif t >= 8:
            return "冷，穿厚外套或薄羽绒。"
        elif t >= 4:
            return "很冷，穿大衣加保暖内衣。"
        else:
            return "严寒，穿厚羽绒服重保暖。"
    except:
        return "请据体感气温调整着装。"

def get_weather_icon(weather_str):
    if not weather_str:
        return "S"  
    if "晴" in weather_str:
        hour = (datetime.utcnow() + timedelta(hours=8)).hour
        return "B" if 6 <= hour < 18 else "C"
    if "多云" in weather_str or "少云" in weather_str or "晴间多云" in weather_str:
        return "Y"  
    if "阴" in weather_str:
        return "N"  
    if "冰雹" in weather_str:
        return "X"  
    if "雷" in weather_str:
        return "O"  
    if "大雪" in weather_str or "暴雪" in weather_str or "中雪" in weather_str:
        return "W"  
    if "雪" in weather_str or "阵雪" in weather_str:
        return "U"  
    if "阵雨" in weather_str:
        return "T"  
    if "大雨" in weather_str or "暴雨" in weather_str or "中雨" in weather_str:
        return "R"  
    if "雨" in weather_str or "毛毛雨" in weather_str or "细雨" in weather_str:
        return "Q"  
    if "雾" in weather_str:
        return "L"  
    if "霾" in weather_str or "尘" in weather_str or "扬沙" in weather_str or "沙尘" in weather_str:
        return "M"  
    if "大风" in weather_str or "狂风" in weather_str or "疾风" in weather_str or "飓风" in weather_str or "台风" in weather_str or "阵风" in weather_str or "飑" in weather_str:
        return "F"  
    if "风" in weather_str:
        return "E"  
    return "S"  

def truncate_text_by_pixels(draw, text, font, max_width):
    current_line = ""
    for char in text:
        test_line = current_line + char
        try:
            w = draw.textlength(test_line, font=font)
        except AttributeError:
            w = draw.textbbox((0, 0), test_line, font=font)[2] - draw.textbbox((0, 0), test_line, font=font)[0]
        if w <= max_width:
            current_line = test_line
        else:
            break  
    return current_line

# 推送图片到单个设备
def push_image(img, page_id, mac=None):
    if str(page_id) not in ENABLED_PAGES:
        return
        
    img_path = f"page_{page_id}.png"
    img.save(img_path)
    api_headers = {"X-API-Key": API_KEY}
    data = {"dither": "true", "pageId": str(page_id)}
    
    # 如果指定了 mac，只推送到该设备
    if mac:
        devices = [mac]
    else:
        devices = [c["mac"] for c in DEVICE_CONFIGS]
    
    for device_mac in devices:
        push_url = f"https://cloud.zectrix.com/open/v1/devices/{device_mac}/display/image"
        try:
            with open(img_path, "rb") as f:
                files = {"images": (img_path, f, "image/png")}
                res = requests.post(push_url, headers=api_headers, files=files, data=data)
                print(f"✅ 设备 [{device_mac}] Page {page_id} 推送成功: {res.status_code}")
        except Exception as e:
            print(f"❌ 设备 [{device_mac}] Page {page_id} 推送失败: {e}")

# --- 节气与农历 ---
def get_solar_term(year, month, day):
    term_table = {
        (2024,2,4):"立春", (2024,2,19):"雨水", (2024,3,5):"惊蛰", (2024,3,20):"春分",
        (2024,4,4):"清明", (2024,4,19):"谷雨", (2024,5,5):"立夏", (2024,5,20):"小满",
        (2024,6,5):"芒种", (2024,6,21):"夏至", (2024,7,6):"小暑", (2024,7,22):"大暑",
        (2024,8,7):"立秋", (2024,8,22):"处暑", (2024,9,7):"白露", (2024,9,22):"秋分",
        (2024,10,8):"寒露", (2024,10,23):"霜降", (2024,11,7):"立冬", (2024,11,22):"小雪",
        (2024,12,6):"大雪", (2024,12,21):"冬至",
        (2025,1,5):"小寒", (2025,1,20):"大寒", (2025,2,3):"立春", (2025,2,18):"雨水",
        (2025,3,5):"惊蛰", (2025,3,20):"春分", (2025,4,4):"清明", (2025,4,20):"谷雨",
        (2025,5,5):"立夏", (2025,5,21):"小满", (2025,6,5):"芒种", (2025,6,21):"夏至",
        (2025,7,7):"小暑", (2025,7,22):"大暑", (2025,8,7):"立秋", (2025,8,23):"处暑",
        (2025,9,7):"白露", (2025,9,22):"秋分", (2025,10,8):"寒露", (2025,10,23):"霜降",
        (2025,11,7):"立冬", (2025,11,22):"小雪", (2025,12,7):"大雪", (2025,12,21):"冬至",
        (2026,1,5):"小寒", (2026,1,20):"大寒", (2026,2,4):"立春", (2026,2,18):"雨水",
        (2026,3,5):"惊蛰", (2026,3,20):"春分", (2026,4,5):"清明", (2026,4,20):"谷雨",
        (2026,5,5):"立夏", (2026,5,21):"小满", (2026,6,6):"芒种", (2026,6,21):"夏至",
        (2026,7,7):"小暑", (2026,7,23):"大暑", (2026,8,7):"立秋", (2026,8,23):"处暑",
        (2026,9,7):"白露", (2026,9,23):"秋分", (2026,10,8):"寒露", (2026,10,23):"霜降",
        (2026,11,7):"立冬", (2026,11,22):"小雪", (2026,12,7):"大雪", (2026,12,21):"冬至",
        (2027,1,5):"小寒", (2027,1,20):"大寒", (2027,2,4):"立春", (2027,2,19):"雨水",
        (2027,3,6):"惊蛰", (2027,3,21):"春分", (2027,4,5):"清明", (2027,4,20):"谷雨",
    }
    return term_table.get((year, month, day), None)

def get_lunar_or_festival(y, m, d):
    """获取农历节日/节气/公历节日，非特殊日期返回短农历（如'十六'）"""
    term = get_solar_term(y, m, d)
    if term: return term
    solar_fests = {
        (1,1):"元旦", (2,14):"情人节", (3,8):"妇女节", (4,1):"愚人节",
        (5,1):"劳动节", (6,1):"儿童节", (7,1):"建党节", (8,1):"建军节",
        (9,10):"教师节", (10,1):"国庆节", (12,25):"圣诞节"
    }
    if (m, d) in solar_fests: return solar_fests[(m, d)]
    try:
        lunar = ZhDate.from_datetime(datetime(y, m, d))
        lunar_fests = {(1,1):"春节", (1,15):"元宵", (5,5):"端午", (7,7):"七夕", (7,15):"中元", (8,15):"中秋", (9,9):"重阳", (12,30):"除夕"}
        if (lunar.lunar_month, lunar.lunar_day) in lunar_fests:
            return lunar_fests[(lunar.lunar_month, lunar.lunar_day)]
        # 只返回农历日（如"十六"），不带年份
        lunar_days = ['','初一','初二','初三','初四','初五','初六','初七','初八','初九','初十',
                      '十一','十二','十三','十四','十五','十六','十七','十八','十九','二十',
                      '廿一','廿二','廿三','廿四','廿五','廿六','廿七','廿八','廿九','三十']
        return lunar_days[lunar.lunar_day] if lunar.lunar_day <= 30 else ""
    except:
        return ""

# --- 今日页面生成（日历网格）---
def task_calendar():
    if "3" not in ENABLED_PAGES: return
    print("生成 Page 3: 日历...")
    img = Image.new('1', (400, 300), color=255)
    draw = ImageDraw.Draw(img)
    now = datetime.utcnow() + timedelta(hours=8)
    y, m, today = now.year, now.month, now.day

    # 顶部：大月份数字 + 英文月名 + 年份
    draw.text((20, 10), str(m), font=font_huge, fill=0)
    draw.text((90, 20), now.strftime("%B"), font=font_title, fill=0)
    draw.text((90, 48), str(y), font=font_item, fill=0)
    draw.line([(20, 78), (380, 78)], fill=0, width=2)

    # 星期表头
    headers = ["日", "一", "二", "三", "四", "五", "六"]
    col_w = 53
    for i, h in enumerate(headers):
        draw.text((25 + i*col_w, 88), h, font=font_small, fill=0)

    # 日历网格
    calendar.setfirstweekday(calendar.SUNDAY)
    cal = calendar.monthcalendar(y, m)
    curr_y, row_h = 115, 38
    for week in cal:
        for c, day in enumerate(week):
            if day != 0:
                dx = 25 + c * col_w
                if day == today:
                    draw.rounded_rectangle([(dx-3, curr_y-2), (dx+35, curr_y+32)], radius=5, outline=0)
                draw.text((dx+2, curr_y), str(day), font=font_item, fill=0)
                bottom_text = get_lunar_or_festival(y, m, day)
                if bottom_text:
                    if len(bottom_text) > 3:
                        try:
                            font_smaller = ImageFont.truetype(FONT_PATH, 10)
                            draw.text((dx+2, curr_y+18), bottom_text, font=font_smaller, fill=0)
                        except:
                            draw.text((dx+2, curr_y+18), bottom_text[:3], font=font_tiny, fill=0)
                    else:
                        draw.text((dx+2, curr_y+18), bottom_text, font=font_tiny, fill=0)
        curr_y += row_h

    # 日历页面推送到所有设备
    all_macs = [c["mac"] for c in DEVICE_CONFIGS]
    for mac in all_macs:
        push_image(img, 3, mac)

# --- 热搜页面生成 ---
def get_hotlist():
    if HOTLIST_SOURCE == "zhihu":
        try:
            url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            data = resp.json()
            return [{"title": item.get("target", {}).get("title", ""), "desc": item.get("target", {}).get("excerpt", "")} for item in data.get("data", [])]
        except Exception as e:
            print(f"获取知乎热搜失败: {e}")
            return []
    elif HOTLIST_SOURCE == "bilibili":
        try:
            url = "https://app.bilibili.com/x/v2/search/trending/ranking?limit=50"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            data = resp.json()
            return [{"title": item.get("keyword", ""), "desc": item.get("show_name", "")} for item in data.get("data", {}).get("list", [])]
        except Exception as e:
            print(f"获取B站热搜失败: {e}")
            return []
    elif HOTLIST_SOURCE == "github":
        try:
            url = "https://github.com/trending?since=daily"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            repos = re.findall(r'<h2 class="h3 lh-condensed">.*?<a href="(.*?)"', resp.text, re.DOTALL)
            return [{"title": repo.strip().lstrip("/"), "desc": ""} for repo in repos[:50]]
        except Exception as e:
            print(f"获取GitHub热搜失败: {e}")
            return []
    return []

def task_hotlist():
    if "1" not in ENABLED_PAGES and "2" not in ENABLED_PAGES:
        return

    source_map = {"zhihu": "知乎热榜", "bilibili": "B站热搜", "github": "GitHub 热门"}
    raw_hotlist = get_hotlist()
    titles = [item.get("title", "") for item in raw_hotlist]
    title_display = source_map.get(HOTLIST_SOURCE, "热门看板")

    def wrap_text_by_pixels(draw, text, font, max_width):
        lines = []
        current_line = ""
        for char in text:
            test_line = current_line + char
            try:
                w = draw.textlength(test_line, font=font)
            except AttributeError:
                w = draw.textbbox((0,0), test_line, font=font)[2]
            if w <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
        return lines

    def draw_list(draw, page_title, items, start_idx):
        draw.rounded_rectangle([(10, 10), (390, 45)], radius=8, fill=0)
        draw.text((20, 15), page_title, font=font_title, fill=255)

        y, last_idx = 55, start_idx
        item_gap = 12
        line_height = 23

        for i in range(start_idx, len(items)):
            lines = wrap_text_by_pixels(draw, items[i], font_item, max_width=340)
            required_h = len(lines) * line_height
            if y + required_h > 295:
                break

            current_num = i + 1
            draw.rounded_rectangle([(10, y), (36, y+24)], radius=6, fill=0)
            num_x = 18 if current_num < 10 else 11
            draw.text((num_x, y+3), str(current_num), font=font_small, fill=255)

            curr_y = y + 1
            for line in lines:
                draw.text((45, curr_y), line, font=font_item, fill=0)
                curr_y += line_height

            y += max(24, required_h) + item_gap
            last_idx = i + 1

            if y < 290:
                draw.line([(45, y - item_gap/2), (380, y - item_gap/2)], fill=0, width=1)

        return last_idx

    all_macs = [c["mac"] for c in DEVICE_CONFIGS]
    next_s = 0
    if "1" in ENABLED_PAGES:
        print("生成 Page 1: 热搜 (上)...")
        img1 = Image.new('1', (400, 300), color=255)
        next_s = draw_list(ImageDraw.Draw(img1), f"◆ {title_display} (一)", titles, 0)
        for mac in all_macs:
            push_image(img1, 1, mac)

    if "2" in ENABLED_PAGES:
        print("生成 Page 2: 热搜 (下)...")
        img2 = Image.new('1', (400, 300), color=255)
        start_index = next_s if "1" in ENABLED_PAGES else 7
        draw_list(ImageDraw.Draw(img2), f"◆ {title_display} (二)", titles, start_index)
        for mac in all_macs:
            push_image(img2, 2, mac)

# --- 日程页面生成 ---
def get_todo_data():
    if not API_KEY:
        return []
    try:
        url = "https://cloud.zectrix.com/open/v1/todos"
        headers = {"X-API-Key": API_KEY}
        res = requests.get(url, headers=headers, timeout=10).json()
        
        raw_todos = []
        if isinstance(res, list):
            raw_todos = res
        elif isinstance(res, dict):
            raw_todos = res.get("data", []) or res.get("todos", []) or []
            
        seen = set()
        deduped_todos = []
        for todo in raw_todos:
            if isinstance(todo, dict):
                todo_key = (todo.get("title"), todo.get("dueDate"), todo.get("dueTime"))
                if todo_key not in seen:
                    seen.add(todo_key)
                    deduped_todos.append(todo)
        return deduped_todos
    except Exception as e:
        print(f"❌ 获取云端日程异常: {e}")
        return []

# --- HA 室内数据获取 ---
def get_ha_indoor_data(temp_sensor, humid_sensor):
    """从 Home Assistant 获取室内温湿度数据"""
    result = {"indoor_temp": "--", "indoor_humidity": "--"}
    
    if not HA_URL or not HA_TOKEN:
        print("⚠️ 未配置 HA_URL 或 HA_TOKEN")
        return result
    
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 获取温度
    if temp_sensor:
        try:
            url = f"{HA_URL}/api/states/{temp_sensor}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                state = data.get("state", "")
                unit = data.get("attributes", {}).get("unit_of_measurement", "°C")
                result["indoor_temp"] = f"{state}{unit}"
            else:
                print(f"⚠️ 获取温度传感器失败: {resp.status_code}")
        except Exception as e:
            print(f"❌ 获取温度传感器异常: {e}")
    
    # 获取湿度
    if humid_sensor:
        try:
            url = f"{HA_URL}/api/states/{humid_sensor}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                state = data.get("state", "")
                unit = data.get("attributes", {}).get("unit_of_measurement", "%")
                result["indoor_humidity"] = f"{state}{unit}"
            else:
                print(f"⚠️ 获取湿度传感器失败: {resp.status_code}")
        except Exception as e:
            print(f"❌ 获取湿度传感器异常: {e}")
    
    return result

# --- 天气缓存 ---
WEATHER_CACHE_FILE = "weather_cache.json"

def _load_weather_cache():
    try:
        if os.path.exists(WEATHER_CACHE_FILE):
            with open(WEATHER_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return None

def _save_weather_cache(data):
    try:
        with open(WEATHER_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("💾 天气数据已缓存")
    except Exception as e:
        print(f"⚠️ 缓存写入失败: {e}")

# --- 混合天气获取 ---
def get_hybrid_weather(city_code, location):
    """获取指定城市的天气数据"""
    result = {
        "weather": "未知", "temp_curr": 0, 
        "temp_low": 0, "temp_high": 0, "wind_info": "无数据", "humidity": "0%", 
        "feel_temp": "N/A", "sunrise": "--:--", "sunset": "--:--", "forecasts": [],
        "request_failed": False
    }
    
    if not AMAP_KEY:
        print("⚠️ 未设置 AMAP_WEATHER_KEY")
        result["request_failed"] = True
        return result

    # --- 高德实时天气 ---
    amap_live_ok = False
    try:
        base_url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={city_code}&key={AMAP_KEY}&extensions=base"
        base_resp = requests.get(base_url, timeout=10).json()
        if base_resp.get("status") == "1" and base_resp.get("lives"):
            live = base_resp["lives"][0]
            result["weather"] = live.get("weather", "未知")
            result["temp_curr"] = int(live.get("temperature", 0))
            result["humidity"] = live.get("humidity", "0") + "%"
            wind_power_raw = live.get("windpower", "0")
            wind_direction = live.get("winddirection", "")
            wind_num = re.search(r'\d+', wind_power_raw)
            wind_power = wind_num.group(0) if wind_num else "0"
            result["wind_info"] = f"{wind_power}级 {wind_direction}"
            amap_live_ok = True
    except Exception as e:
        print(f"❌ 高德实时请求异常: {e}")

    # --- 高德预报天气 ---
    amap_forecast_ok = False
    try:
        all_url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={city_code}&key={AMAP_KEY}&extensions=all"
        all_resp = requests.get(all_url, timeout=10).json()
        if all_resp.get("status") == "1" and all_resp.get("forecasts"):
            casts = all_resp["forecasts"][0].get("casts", [])
            if len(casts) >= 1:
                result["temp_low"] = int(casts[0].get("nighttemp", 0))
                result["temp_high"] = int(casts[0].get("daytemp", 0))
            for idx in [1, 2, 3]:
                if idx < len(casts):
                    day = casts[idx]
                    result["forecasts"].append({
                        "date": day.get("date", "")[5:],
                        "weather": day.get("dayweather", "未知"),
                        "temp_low": int(day.get("nighttemp", 0)),
                        "temp_high": int(day.get("daytemp", 0))
                    })
            amap_forecast_ok = True
    except Exception as e:
        print(f"❌ 高德预报请求异常: {e}")

    # --- wttr.in 日出日落 ---
    wttr_ok = False
    try:
        wttr_url = f"https://wttr.in/{location}?format=j1&lang=zh"
        wttr_resp = requests.get(wttr_url, timeout=15).json()
        astro = wttr_resp['weather'][0]['astronomy'][0]
        result["sunrise"] = astro['sunrise']
        result["sunset"] = astro['sunset']
        wttr_ok = True
    except Exception as e:
        print(f"❌ wttr.in 请求异常: {e}")

    # --- 判断是否需要回退到缓存 ---
    if not amap_live_ok:
        print("⚠️ 高德实时请求失败，尝试使用缓存数据...")
        cached = _load_weather_cache()
        if cached:
            if not amap_forecast_ok:
                cached["request_failed"] = True
                return cached
            else:
                result["weather"] = cached.get("weather", "未知")
                result["temp_curr"] = cached.get("temp_curr", 0)
                result["humidity"] = cached.get("humidity", "0%")
                result["wind_info"] = cached.get("wind_info", "无数据")
                result["feel_temp"] = cached.get("feel_temp", "N/A")
                result["sunrise"] = cached.get("sunrise", "--:--") if not wttr_ok else result["sunrise"]
                result["sunset"] = cached.get("sunset", "--:--") if not wttr_ok else result["sunset"]
                result["request_failed"] = True
                result["_cache_time"] = cached.get("_cache_time", "未知")
                _save_weather_cache(result)
                return result
        else:
            if not amap_forecast_ok:
                result["request_failed"] = True
                return result

    # --- 成功获取数据，保存缓存 ---
    now_beijing = datetime.utcnow() + timedelta(hours=8)
    result["_cache_time"] = now_beijing.strftime("%Y-%m-%d %H:%M")
    result["request_failed"] = False
    _save_weather_cache(result)
    return result

# --- 计算体感温度（基于室内温湿度） ---
def calculate_feel_temp(indoor_temp_str, indoor_humid_str):
    """基于室内温湿度计算体感温度（Heat Index公式，美国国家气象局）"""
    try:
        temp_str = indoor_temp_str.replace("°C", "").replace("°", "").strip()
        t_c = float(temp_str)
        
        humid_str = indoor_humid_str.replace("%", "").strip()
        rh = float(humid_str)
        
        # 转换为华氏度
        t_f = t_c * 9.0 / 5.0 + 32.0
        
        # Heat Index 公式（华氏度）
        hi_f = (-42.379 
                + 2.04901523 * t_f 
                + 10.14333127 * rh 
                - 0.22475541 * t_f * rh 
                - 6.83783e-3 * t_f**2 
                - 5.481717e-2 * rh**2 
                + 1.22874e-3 * t_f**2 * rh 
                + 8.5282e-4 * t_f * rh**2 
                - 1.99e-6 * t_f**2 * rh**2)
        
        # 转换回摄氏度
        feel_temp = (hi_f - 32.0) * 5.0 / 9.0
        return f"{round(feel_temp, 1)}°C"
    except Exception as e:
        print(f"⚠️ 计算体感温度失败: {e}")
        return "--"

# --- 任务：天气看板（单设备） ---
def task_weather_dashboard(device_config):
    """为单个设备生成天气看板"""
    if "4" not in ENABLED_PAGES: return
    
    mac = device_config["mac"]
    city_code = device_config["city"]
    location = device_config["location"]
    temp_sensor = device_config["temp_sensor"]
    humid_sensor = device_config["humid_sensor"]
    device_name = device_config["name"]
    
    print(f"生成 Page 4: 天气看板 ({device_name})...")
    img = Image.new('1', (400, 300), color=255)
    draw = ImageDraw.Draw(img)

    weather = get_hybrid_weather(city_code, location)
    
    # 获取室内数据
    indoor = get_ha_indoor_data(temp_sensor, humid_sensor)
    
    # 计算体感温度
    feel_temp = calculate_feel_temp(indoor["indoor_temp"], indoor["indoor_humidity"])
    outdoor_feel = calculate_outdoor_feel(weather['temp_curr'], weather['humidity'])
    
    if weather["temp_curr"] == 0 and not weather["forecasts"]:
        draw.text((20, 50), "天气数据获取失败", font=font_item, fill=0)
        push_image(img, 4, mac)
        return

    # 1. 日期行设置
    now_beijing = datetime.utcnow() + timedelta(hours=8)
    youbi_list = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
    youbi = youbi_list[now_beijing.weekday()]
    date_display = f"{device_name} | {now_beijing.month}月{now_beijing.day}日 {youbi}"
    
    draw.text((25, 15), date_display, font=font_item, fill=0)
    
    update_time = now_beijing.strftime("%I:%M %p")
    time_text = f"更新: {update_time}"
    try:
        time_w = draw.textlength(time_text, font=font_item)
    except AttributeError:
        time_w = draw.textbbox((0, 0), time_text, font=font_item)[2] - draw.textbbox((0, 0), time_text, font=font_item)[0]
    draw.text((385 - time_w, 15), time_text, font=font_item, fill=0)

    # 2. 当日最高最低气温
    draw.text((25, 45), f"{weather['temp_low']}° / {weather['temp_high']}°", font=font_item, fill=0)
    
    # 3. 实时温度
    curr_temp_str = f"{weather['temp_curr']}°"
    draw.text((25, 65), curr_temp_str, font=font_48, fill=0)
    
    try:
        temp_w = draw.textlength(curr_temp_str, font=font_48)
    except AttributeError:
        temp_w = draw.textbbox((0, 0), curr_temp_str, font=font_48)[2] - draw.textbbox((0, 0), curr_temp_str, font=font_48)[0]
    
    wx_x = 25 + temp_w + 12
    # 天气文字底部对齐实时温度
    draw.text((wx_x, 77), weather['weather'], font=font_36, fill=0)
    
    # 🌟 4. 实时大天气图标
    if weather.get("request_failed"):
        draw.text((wx_x, 55), "天气请求失败", font=font_small, fill=0)
    else:
        current_icon = get_weather_icon(weather['weather'])
        draw.text((wx_x, 42), current_icon, font=font_weather_icon_large, fill=0)

    # 🌟 室外温湿度 - 天气文字右边双排显示（font_item，行距18px对齐font_36高度）
    try:
        weather_text_w = draw.textlength(weather['weather'], font=font_36)
    except AttributeError:
        weather_text_w = draw.textbbox((0, 0), weather['weather'], font=font_36)[2]
    outdoor_x = wx_x + int(weather_text_w) + 10
    draw.text((outdoor_x, 48), f"{weather['temp_curr']}° {weather['humidity']}", font=font_item, fill=0)
    draw.text((outdoor_x, 66), f"外体感 {outdoor_feel}", font=font_item, fill=0)

    # 🌟 侧边右侧黑色背景框 - 室内/体感（右边界与日程区域对齐）
    draw.rounded_rectangle([(240, 40), (385, 116)], radius=8, outline=0, fill=0)
    draw.text((250, 48), f"室内 {indoor['indoor_temp']} {indoor['indoor_humidity']}", font=font_small, fill=255)
    draw.text((250, 72), f"内体感 {feel_temp}", font=font_small, fill=255)
    draw.text((250, 96), f"外体感 {outdoor_feel}", font=font_small, fill=255)

    # 🌟 日出日落 + 风力（同一行，下移）
    draw.text((25, 145), "A", font=font_weather_icon_small, fill=0, anchor="lm")
    draw.text((45, 145), weather['sunrise'], font=font_item, fill=0, anchor="lm")
    
    draw.text((145, 145), "J", font=font_weather_icon_small, fill=0, anchor="lm")
    draw.text((165, 145), weather['sunset'], font=font_item, fill=0, anchor="lm")
    
    # 风力信息放在日出日落行右侧
    wind_text = f"{weather['wind_info']}风"
    try:
        wind_w = draw.textlength(wind_text, font=font_item)
    except AttributeError:
        wind_w = draw.textbbox((0, 0), wind_text, font=font_item)[2]
    draw.text((270, 145), wind_text, font=font_item, fill=0, anchor="lm")
    
    draw.line([(20, 155), (380, 155)], fill=0, width=1)
    
    # 时区窗口日程过滤逻辑
    all_todos = get_todo_data()
    today_str = now_beijing.strftime("%Y-%m-%d")
    is_after_1030 = now_beijing.hour > 22 or (now_beijing.hour == 22 and now_beijing.minute >= 30)
    
    if is_after_1030:
        target_date_str = (now_beijing + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        target_date_str = today_str
    
    target_todos = [t for t in all_todos if t.get("dueDate") == target_date_str]
    target_todos = [t for t in target_todos if t.get("status") in [0, "0", None]]
    target_todos.sort(key=lambda x: x.get("dueTime", ""))
    display_todos = target_todos[:2] if is_after_1030 else target_todos[:3]

    # 🌟 5. 未来预报前两列
    for i in range(2):
        if i < len(weather['forecasts']):
            day = weather['forecasts'][i]
            x = [20, 145][i]
            draw.text((x, 168), day["date"], font=font_item, fill=0)
            
            weather_text = day['weather']
            draw.text((x, 193), weather_text, font=font_item, fill=0) 
            
            try:
                text_w = draw.textlength(weather_text, font=font_item)
            except AttributeError:
                text_w = draw.textbbox((0, 0), weather_text, font=font_item)[2] - draw.textbbox((0, 0), weather_text, font=font_item)[0]
                
            icon_char = get_weather_icon(weather_text)
            draw.text((x + text_w + 4, 193), icon_char, font=font_weather_icon_small, fill=0) 
            
            draw.text((x, 213), f"{day['temp_low']}°~{day['temp_high']}°", font=font_item, fill=0)

    # 渲染第三列 (x=270)
    if display_todos:
        draw.rounded_rectangle([(260, 158), (385, 238)], radius=8, outline=0, fill=0)
        todo_y = 164
        if is_after_1030:
            draw.text((268, todo_y), "明日：", font=font_small, fill=255)
            todo_y += 24
            
        for todo in display_todos:
            title_clean = todo.get("title", "").replace("[日历]", "").strip()
            time_str = todo.get("dueTime", "")
            display_text = f"{time_str} {title_clean}".strip() if time_str else title_clean
            
            truncated_line = truncate_text_by_pixels(draw, display_text, font_small, max_width=112)
            draw.text((268, todo_y), truncated_line, font=font_small, fill=255)
            todo_y += 24
    else:
        # 🌟 6. 兜底：无日程显示第三列预报
        if len(weather['forecasts']) >= 3:
            day = weather['forecasts'][2]
            x = 270
            draw.text((x, 168), day["date"], font=font_item, fill=0)
            
            weather_text = day['weather']
            draw.text((x, 193), weather_text, font=font_item, fill=0)
            
            try:
                text_w = draw.textlength(weather_text, font=font_item)
            except AttributeError:
                text_w = draw.textbbox((0, 0), weather_text, font=font_item)[2] - draw.textbbox((0, 0), weather_text, font=font_item)[0]
                
            icon_char = get_weather_icon(weather_text)
            draw.text((x + text_w + 4, 193), icon_char, font=font_weather_icon_small, fill=0)
            
            draw.text((x, 213), f"{day['temp_low']}°~{day['temp_high']}°", font=font_item, fill=0)


    advice = get_clothing_advice(outdoor_feel)
    draw.line([(20, 243), (380, 243)], fill=0, width=1)
    advice_lines = [advice[i:i+18] for i in range(0, len(advice), 18)]
    for i, line in enumerate(advice_lines[:2]):
        draw.text((20, 255 + i*24), f"[穿衣建议] {line}", font=font_item, fill=0)

    push_image(img, 4, mac)

# ================= 主程序 =================
if __name__ == "__main__":
    if not API_KEY:
        print("❌ 错误: 请检查 ZECTRIX_API_KEY")
        exit(1)
    
    if not DEVICE_CONFIGS:
        print("❌ 错误: 未配置任何设备，请检查 HOME_MAC 或 OFFICE_MAC")
        exit(1)
        
    print(f"🚀 开始向 {len(DEVICE_CONFIGS)} 个设备执行墨水屏推送任务...")
    
    # 热搜和日历页面推送到所有设备（共用）
    task_hotlist()
    task_calendar()
    
    # 天气页面每个设备独立生成和推送
    for config in DEVICE_CONFIGS:
        print(f"\n📱 处理设备: {config['name']} ({config['mac']})")
        task_weather_dashboard(config)
    
    print("\n🎉 所有任务执行完毕！")

# --- 计算室外体感温度（澳大利亚气象局公式） ---
def calculate_outdoor_feel(temp_str, humidity_str):
    """基于室外温湿度计算体感温度（AT = T + 0.33*e - 4.00，澳大利亚气象局）"""
    try:
        t = float(str(temp_str).replace("°C", "").replace("°", "").strip())
        rh = float(str(humidity_str).replace("%", "").strip())
        # 水汽压 e = RH/100 * 6.105 * exp(17.27*T/(237.7+T))
        import math
        e = rh / 100.0 * 6.105 * math.exp(17.27 * t / (237.7 + t))
        at = t + 0.33 * e - 4.00
        return f"{round(at, 1)}°C"
    except Exception as e:
        print(f"⚠️ 计算室外体感失败: {e}")
        return "--"
