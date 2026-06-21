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

def get_clothing_advice(temp, humidity_str):
    try:
        t = int(temp)
        h = int(humidity_str.replace('%', '')) if isinstance(humidity_str, str) else int(humidity_str)
        if t >= 28:
            return "闷热，穿透气短袖短裤。" if h >= 70 else "炎热，穿薄短袖并防晒。"
        elif t > 22:
            return "湿热，建议穿宽松T恤。" if h >= 70 else "舒适，穿T恤配单裤即可。"
        elif t > 16:
            return "偏湿凉，穿长袖加薄外套。" if h >= 70 else "清凉，穿长袖衬衫或卫衣。"
        elif t > 10:
            return "湿冷透骨，建议穿厚夹克。" if h >= 70 else "偏冷，穿风衣或保暖毛衣。"
        elif t > 5:
            return "湿冷，穿大衣及保暖内衣。" if h >= 60 else "干冷，建议穿大衣薄羽绒。"
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
        return lunar.chinese()
    except:
        return ""

# --- 今日页面生成 ---
def task_calendar():
    if "3" not in ENABLED_PAGES: return
    print("生成 Page 3: 日历...")
    img = Image.new('1', (400, 300), color=255)
    draw = ImageDraw.Draw(img)
    now = datetime.utcnow() + timedelta(hours=8)
    year, month, day = now.year, now.month, now.day
    weekdays = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
    date_str = f"{year}年{month}月{day}日 {weekdays[now.weekday()]}"
    draw.text((25, 25), date_str, font=font_title, fill=0)
    try:
        lunar = ZhDate.from_datetime(now)
        lunar_str = f"农历 {lunar.chinese()}"
        draw.text((25, 65), lunar_str, font=font_item, fill=0)
    except:
        pass
    term = get_solar_term(year, month, day)
    fest = get_lunar_or_festival(year, month, day)
    if term or fest:
        text = f"今日：{term or ''} {fest or ''}".strip()
        draw.text((25, 100), text, font=font_item, fill=0)
    try:
        with open("holiday.json", "r", encoding="utf-8") as f:
            holidays = json.load(f)
            today_date = f"{year}-{month:02d}-{day:02d}"
            for h in holidays.get("days", []):
                if h.get("date") == today_date and h.get("isOffDay"):
                    draw.text((25, 130), f"🎉 {h.get('name', '假期')}", font=font_item, fill=0)
                    break
    except:
        pass
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
    if "1" not in ENABLED_PAGES and "2" not in ENABLED_PAGES: return
    hotlist = get_hotlist()
    if not hotlist: return
    now_beijing = datetime.utcnow() + timedelta(hours=8)
    update_time = now_beijing.strftime("%H:%M")
    all_macs = [c["mac"] for c in DEVICE_CONFIGS]
    for page_idx in range(2):
        if str(page_idx + 1) not in ENABLED_PAGES: continue
        img = Image.new('1', (400, 300), color=255)
        draw = ImageDraw.Draw(img)
        source_names = {"zhihu": "知乎", "bilibili": "哔哩哔哩", "github": "GitHub"}
        title = f"{source_names.get(HOTLIST_SOURCE, HOTLIST_SOURCE)} 热搜"
        draw.text((25, 15), title, font=font_title, fill=0)
        try:
            title_w = draw.textlength(title, font=font_title)
        except AttributeError:
            title_w = draw.textbbox((0, 0), title, font=font_title)[2]
        update_text = f"更新: {update_time}"
        try:
            update_w = draw.textlength(update_text, font=font_small)
        except AttributeError:
            update_w = draw.textbbox((0, 0), update_text, font=font_small)[2]
        draw.text((385 - update_w, 21), update_text, font=font_small, fill=0)
        draw.line([(20, 45), (380, 45)], fill=0, width=1)
        start_idx = page_idx * 25
        end_idx = start_idx + 25
        current_hotlist = hotlist[start_idx:end_idx]
        for i, item in enumerate(current_hotlist):
            y = 55 + i * 10
            rank = start_idx + i + 1
            rank_str = f"{rank:2d}"
            title = item.get("title", "")
            truncated_title = truncate_text_by_pixels(draw, title, font_tiny, max_width=300)
            draw.text((25, y), f"{rank_str}.", font=font_tiny, fill=0)
            draw.text((55, y), truncated_title, font=font_tiny, fill=0)
        # 热搜页面推送到所有设备
        for mac in all_macs:
            push_image(img, page_idx + 1, mac)

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
    """基于室内温湿度计算体感温度（无风速项）"""
    try:
        temp_str = indoor_temp_str.replace("°C", "").replace("°", "").strip()
        t = float(temp_str)
        
        humid_str = indoor_humid_str.replace("%", "").strip()
        h = float(humid_str)
        
        e = (h / 100.0) * 6.105 * math.exp((17.27 * t) / (237.7 + t))
        feel_temp = t + 0.33 * e - 4.00
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
    
    # 计算体感温度（基于室内温湿度）
    feel_temp = calculate_feel_temp(indoor["indoor_temp"], indoor["indoor_humidity"])
    
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

    # 🌟 侧边右侧黑色背景框 - 室内/室外/体感（右边界与日程区域对齐）
    draw.rounded_rectangle([(240, 40), (385, 130)], radius=8, outline=0, fill=0)
    draw.text((250, 48), f"室内 {indoor['indoor_temp']} {indoor['indoor_humidity']}", font=font_small, fill=255)
    draw.text((250, 72), f"室外 {weather['humidity']}", font=font_small, fill=255)
    draw.text((250, 96), f"体感 {feel_temp}", font=font_small, fill=255)

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


    advice = get_clothing_advice(weather['temp_curr'], indoor['indoor_humidity'])
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
