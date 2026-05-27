import os
import requests
import calendar
import re
import math
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from zhdate import ZhDate

# =====================================================================
# 🌟 第一部分：用户自定义区（想改什么，直接在这里改文字和数字） 🌟
# =====================================================================

# 1. 控制推送哪几页？
# 墨水屏共 5 页：1=热搜上, 2=热搜下, 3=日历, 4=天气
ENABLED_PAGES = "1,2,3,4"

# 2. 热搜源设置：目前支持 'zhihu', 'bilibili', 'github'
HOTLIST_SOURCE = "bilibili"  # 在这里修改你想看的热搜源

# 3. 天气城市设置
# 高德天气城市代码（默认：常州天宁区 320402）
CITY_ADCODE = "320402"                      

# 日出日落位置（支持拼音，如 "Beijing" 或 "Haidian,Beijing"）
WTTR_LOCATION = "Tianning,Changzhou"            


# =====================================================================
# 🔒 第二部分：核心密钥区（⚠️绝对不要改这里，请在 GitHub Secrets 里配置） 🔒
# =====================================================================
API_KEY = os.environ.get("ZECTRIX_API_KEY")
AMAP_KEY = os.environ.get("AMAP_WEATHER_KEY")

# 🌟 多设备支持：从单个 Secret 中读取逗号分隔的多个 MAC 地址，彻底解决泄露风险
ENV_MAC = os.environ.get("ZECTRIX_MAC", "")

# 按逗号拆分、去除两端空格、过滤空值并去重
raw_mac_list = ENV_MAC.split(',')
TARGET_DEVICES = list(set([m.strip() for m in raw_mac_list if m and m.strip()]))


# =====================================================================
# ⚙️ 第三部分：底层运行逻辑（如果没有报错，不需要修改以下 code） ⚙️
# =====================================================================

# --- 字体设置 ---
FONT_PATH = "font.ttf"                             # 基础常规中文字体
WEATHER_FONT_PATH = "font_weather_icon.ttf"       # 专门的天气图标字体

try:
    font_huge = ImageFont.truetype(FONT_PATH, 65)
    font_title = ImageFont.truetype(FONT_PATH, 24)
    font_item = ImageFont.truetype(FONT_PATH, 18)       # 未来天气中文字体 (18号)
    font_small = ImageFont.truetype(FONT_PATH, 14)
    font_tiny = ImageFont.truetype(FONT_PATH, 11)
    font_48 = ImageFont.truetype(FONT_PATH, 48)
    font_36 = ImageFont.truetype(FONT_PATH, 36)         # 实时天气中文字体 (36号)
    
    # 将图标字体拆分为大、小两组，完美匹配文本字号
    font_weather_icon_large = ImageFont.truetype(WEATHER_FONT_PATH, 36) # 专门匹配实时天气大字 (36号)
    font_weather_icon_small = ImageFont.truetype(WEATHER_FONT_PATH, 18) # 专门匹配未来预报小字 (18号)
except Exception as e:
    print(f"❌ 错误: 字体文件加载失败，请检查 font.ttf 和 font_weather_icon.ttf 是否都在根目录下。错误详情: {e}")
    exit(1)

# 使用更通用的请求头
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
        elif t >= 22:
            return "湿热，建议穿宽松T恤。" if h >= 70 else "舒适，穿T恤配单裤即可。"
        elif t >= 16:
            return "偏湿凉，穿长袖加薄外套。" if h >= 70 else "清凉，穿长袖衬衫或卫衣。"
        elif t >= 10:
            return "湿冷透骨，建议穿厚夹克。" if h >= 70 else "偏冷，穿风衣或保暖毛衣。"
        elif t >= 5:
            return "湿冷，穿大衣及保暖内衣。" if h >= 60 else "干冷，建议穿大衣薄羽绒。"
        else:
            return "严寒，穿厚羽绒服重保暖。"
    except:
        return "请据体感气温调整着装。"

# 精简天气映射函数
def get_weather_icon(weather_str):
    if not weather_str:
        return "S"  
    if "晴" in weather_str:
        hour = (datetime.utcnow() + timedelta(hours=8)).hour
        if 6 <= hour < 18:
            return "B"  
        else:
            return "C"  
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

# 🛠️ 像素级右端强行截断工具函数
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

# 推送图片
def push_image(img, page_id):
    if str(page_id) not in ENABLED_PAGES:
        print(f"⏩ Page {page_id} 未启用，跳过推送。")
        return
        
    img_path = f"page_{page_id}.png"
    img.save(img_path)
    api_headers = {"X-API-Key": API_KEY}
    data = {"dither": "true", "pageId": str(page_id)}
    
    for mac in TARGET_DEVICES:
        push_url = f"https://cloud.zectrix.com/open/v1/devices/{mac}/display/image"
        try:
            with open(img_path, "rb") as f:
                files = {"images": (img_path, f, "image/png")}
                res = requests.post(push_url, headers=api_headers, files=files, data=data)
                print(f"✅ 设备 [{mac}] Page {page_id} 推送成功: {res.status_code}")
        except Exception as e:
            print(f"❌ 设备 [{mac}] Page {page_id} 推送失败: {e}")

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
        lm, ld = lunar.lunar_month, lunar.lunar_day
        lunar_fests = {
            (1,1):"春节", (1,15):"元宵节", (5,5):"端午节",
            (7,7):"七夕节", (8,15):"中秋节", (9,9):"重阳节", (12,30):"除夕"
        }
        if (lm, ld) in lunar_fests: return lunar_fests[(lm, ld)]
        days = ["初一","初二","初三","初四","初五","初六","初七","初八","初九","初十",
                "十一","十二","十三","十四","十五","十六","十七","十八","十九","二十",
                "廿一","廿二","廿三","廿四","廿五","廿六","廿七","廿八","廿九","三十"]
        months = ["正月","二月","三月","四月","五月","六月","七月","八月","九月","十月","冬月","腊月"]
        if ld == 1: return months[lm-1]
        return days[ld-1]
    except:
        return ""

# --- 获取数据的逻辑 ---
def get_hotlist_data(source):
    titles = []
    print(f"正在从 {source} 获取数据...")
    try:
        if source == "zhihu":
            url = "https://api.zhihu.com/topstory/hot-list"
            res = requests.get(url, headers=HEADERS, timeout=10).json()
            titles = [item['target']['title'] for item in res['data']]
        elif source == "bilibili":
            url = "https://api.bilibili.com/x/web-interface/wbi/search/square?limit=20"
            res = requests.get(url, headers=HEADERS, timeout=10).json()
            titles = [item['show_name'] for item in res['data']['trending']['list']]
        elif source == "github":
            date_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            url = f"https://api.github.com/search/repositories?q=stars:>500+created:>{date_str}&sort=stars&order=desc"
            res = requests.get(url, headers=HEADERS, timeout=10).json()
            titles = [f"{item['full_name']}: {item['description'][:50] if item['description'] else 'No desc'}" for item in res['items']]
        else:
            titles = ["不支持的数据源"]
    except Exception as e:
        print(f"获取失败: {e}")
        titles = ["数据获取失败，请检查配置"] * 10
    return titles[:20]

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

# --- 任务：热搜看板 ---
def task_hotlist():
    if "1" not in ENABLED_PAGES and "2" not in ENABLED_PAGES:
        return
        
    source_map = {"zhihu": "知乎热榜", "bilibili": "B站热搜", "github": "GitHub 热门"}
    titles = get_hotlist_data(HOTLIST_SOURCE)
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

    next_s = 0
    if "1" in ENABLED_PAGES:
        print("生成 Page 1: 热搜 (上)...")
        img1 = Image.new('1', (400, 300), color=255)
        next_s = draw_list(ImageDraw.Draw(img1), f"◆ {title_display} (一)", titles, 0)
        push_image(img1, 1)

    if "2" in ENABLED_PAGES:
        print("生成 Page 2: 热搜 (下)...")
        img2 = Image.new('1', (400, 300), color=255)
        start_index = next_s if "1" in ENABLED_PAGES else 7
        draw_list(ImageDraw.Draw(img2), f"◆ {title_display} (二)", titles, start_index)
        push_image(img2, 2)

# --- 任务：日历 ---
def task_calendar():
    if "3" not in ENABLED_PAGES: return
    print("生成 Page 3: 日历...")
    img = Image.new('1', (400, 300), color=255)
    draw = ImageDraw.Draw(img)
    now_utc = datetime.utcnow()
    now = now_utc + timedelta(hours=8)
    y, m, today = now.year, now.month, now.day
    draw.text((20, 10), str(m), font=font_huge, fill=0)
    draw.text((90, 20), now.strftime("%B"), font=font_title, fill=0)
    draw.text((90, 48), str(y), font=font_item, fill=0)
    draw.line([(20, 78), (380, 78)], fill=0, width=2)
    headers = ["日", "一", "二", "三", "四", "五", "六"]
    col_w = 53
    for i, h in enumerate(headers):
        draw.text((25 + i*col_w, 88), h, font=font_small, fill=0)
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
    push_image(img, 3)

# --- 混合天气获取 ---
def get_hybrid_weather():
    result = {
        "weather": "未知", "temp_curr": 0, 
        "temp_low": 0, "temp_high": 0, "wind_info": "无数据", "humidity": "0%", 
        "feel_temp": "N/A", "sunrise": "--:--", "sunset": "--:--", "forecasts": []
    }
    
    if not AMAP_KEY:
        print("⚠️ 未设置 AMAP_WEATHER_KEY")
        return result

    try:
        base_url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={CITY_ADCODE}&key={AMAP_KEY}&extensions=base"
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
            
            try:
                t = result["temp_curr"]
                h = int(live.get("humidity", 50))
                wind_speed_level = int(wind_power)
                v = wind_speed_level * 1.5 
                e = (h / 100.0) * 6.105 * math.exp((17.27 * t) / (237.7 + t))
                feel_temp = t + 0.33 * e - 0.70 * v - 4.00
                result["feel_temp"] = f"{round(feel_temp, 1)}°C"
            except:
                result["feel_temp"] = f"{result['temp_curr']}°C"
    except Exception as e:
        print(f"❌ 高德实时请求异常: {e}")

    try:
        all_url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={CITY_ADCODE}&key={AMAP_KEY}&extensions=all"
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
    except Exception as e:
        print(f"❌ 高德预报请求异常: {e}")

    try:
        wttr_url = f"https://wttr.in/{WTTR_LOCATION}?format=j1&lang=zh"
        wttr_resp = requests.get(wttr_url, timeout=15).json()
        astro = wttr_resp['weather'][0]['astronomy'][0]
        result["sunrise"] = astro['sunrise']
        result["sunset"] = astro['sunset']
    except Exception as e:
        print(f"❌ wttr.in 请求异常: {e}")

    return result

# --- 任务：天气看板 ---
def task_weather_dashboard():
    if "4" not in ENABLED_PAGES: return
    print("生成 Page 4: 混合天气看板...")
    img = Image.new('1', (400, 300), color=255)
    draw = ImageDraw.Draw(img)

    weather = get_hybrid_weather()
    if weather["temp_curr"] == 0 and not weather["forecasts"]:
        draw.text((20, 50), "天气数据获取失败", font=font_item, fill=0)
        push_image(img, 4)
        return

    # 1. 日期行设置
    now_beijing = datetime.utcnow() + timedelta(hours=8)
    youbi_list = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
    youbi = youbi_list[now_beijing.weekday()]
    date_display = f"天宁区 | {now_beijing.month}月{now_beijing.day}日 {youbi}"
    
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
    draw.text((25, 75), curr_temp_str, font=font_48, fill=0)
    
    try:
        temp_w = draw.textlength(curr_temp_str, font=font_48)
    except AttributeError:
        temp_w = draw.textbbox((0, 0), curr_temp_str, font=font_48)[2] - draw.textbbox((0, 0), curr_temp_str, font=font_48)[0]
    
    wx_x = 25 + temp_w + 12
    weather_text = weather['weather']
    current_icon = get_weather_icon(weather_text)
    
    # 🌟 修改点 1：通过计算文字与大图标的像素宽度，实现实时的完美【水平居中对齐】
    try:
        tw = draw.textlength(weather_text, font=font_36)
        iw = draw.textlength(current_icon, font=font_weather_icon_large)
    except AttributeError:
        tw = draw.textbbox((0, 0), weather_text, font=font_36)[2] - draw.textbbox((0, 0), weather_text, font=font_36)[0]
        iw = draw.textbbox((0, 0), current_icon, font=font_weather_icon_large)[2] - draw.textbbox((0, 0), current_icon, font=font_weather_icon_large)[0]
    
    # 计算使图标居中的 X 坐标偏移量
    icon_x = wx_x + (tw - iw) / 2
    
    draw.text((wx_x, 85), weather_text, font=font_36, fill=0)
    draw.text((icon_x, 42), current_icon, font=font_weather_icon_large, fill=0)

    # 侧边右侧黑色背景框
    draw.rounded_rectangle([(260, 45), (385, 130)], radius=8, outline=0, fill=0)
    draw.text((270, 56), f"{weather['wind_info']}风", font=font_small, fill=255)
    draw.text((270, 80), f"湿度 {weather['humidity']}", font=font_small, fill=255)
    draw.text((270, 104), f"体感 {weather['feel_temp']}", font=font_small, fill=255)

    # 🌟 修改点 2：将“日出/日落”文字替换为对应的图标 A 和 J，并利用 anchor="lm" 实现完美的水平线对齐
    draw.text((25, 144), "A", font=font_weather_icon_small, fill=0, anchor="lm")
    draw.text((45, 144), weather['sunrise'], font=font_item, fill=0, anchor="lm")
    
    draw.text((125, 144), "J", font=font_weather_icon_small, fill=0, anchor="lm")
    draw.text((145, 144), weather['sunset'], font=font_item, fill=0, anchor="lm")
    
    draw.line([(20, 160), (380, 160)], fill=0, width=1)
    
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

    # 🌟 修改点 3：未来预报（前两列）。使用 anchor="lm" 将 Y 轴固定在 209 像素，使小图标与天气文本上下完美咬合、对齐
    for i in range(2):
        if i < len(weather['forecasts']):
            day = weather['forecasts'][i]
            x = [20, 145][i]
            draw.text((x, 175), day["date"], font=font_item, fill=0)
            
            day_weather_text = day['weather']
            draw.text((x, 209), day_weather_text, font=font_item, fill=0, anchor="lm") 
            
            try:
                text_w = draw.textlength(day_weather_text, font=font_item)
            except AttributeError:
                text_w = draw.textbbox((0, 0), day_weather_text, font=font_item)[2] - draw.textbbox((0, 0), day_weather_text, font=font_item)[0]
                
            icon_char = get_weather_icon(day_weather_text)
            draw.text((x + text_w + 4, 209), icon_char, font=font_weather_icon_small, fill=0, anchor="lm") 
            
            draw.text((x, 230), f"{day['temp_low']}°~{day['temp_high']}°", font=font_item, fill=0)

    # 渲染第三列 (x=270)
    if display_todos:
        draw.rounded_rectangle([(260, 165), (385, 245)], radius=8, outline=0, fill=0)
        todo_y = 171
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
        # 🌟 修改点 4：无日程显示的第三列预报兜底。同样使用 anchor="lm" 对齐图标与文本
        if len(weather['forecasts']) >= 3:
            day = weather['forecasts'][2]
            x = 270
            draw.text((x, 175), day["date"], font=font_item, fill=0)
            
            day_weather_text = day['weather']
            draw.text((x, 209), day_weather_text, font=font_item, fill=0, anchor="lm")
            
            try:
                text_w = draw.textlength(day_weather_text, font=font_item)
            except AttributeError:
                text_w = draw.textbbox((0, 0), day_weather_text, font=font_item)[2] - draw.textbbox((0, 0), day_weather_text, font=font_item)[0]
                
            icon_char = get_weather_icon(day_weather_text)
            draw.text((x + text_w + 4, 209), icon_char, font=font_weather_icon_small, fill=0, anchor="lm")
            
            draw.text((x, 230), f"{day['temp_low']}°~{day['temp_high']}°", font=font_item, fill=0)


    advice = get_clothing_advice(weather['temp_curr'], weather['humidity'])
    draw.line([(20, 250), (380, 250)], fill=0, width=1)
    advice_lines = [advice[i:i+18] for i in range(0, len(advice), 18)]
    for i, line in enumerate(advice_lines[:2]):
        draw.text((20, 262 + i*24), f"[穿衣建议] {line}", font=font_item, fill=0)

    push_image(img, 4)

# ================= 主程序 =================
if __name__ == "__main__":
    if not API_KEY or not TARGET_DEVICES:
        print("❌ 错误: 请检查密钥和 MAC 地址")
        exit(1)
        
    print(f"🚀 开始向 {len(TARGET_DEVICES)} 个设备执行墨水屏推送任务...")
    task_hotlist()
    task_calendar()
    task_weather_dashboard()
    print("🎉 所有任务执行完毕！")
