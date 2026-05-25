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
MAC_ADDRESS = os.environ.get("ZECTRIX_MAC")
AMAP_KEY = os.environ.get("AMAP_WEATHER_KEY")

# 接口地址（自动拼接）
PUSH_URL = f"https://cloud.zectrix.com/open/v1/devices/{MAC_ADDRESS}/display/image"


# =====================================================================
# ⚙️ 第三部分：底层运行逻辑（如果没有报错，不需要修改以下代码） ⚙️
# =====================================================================

# --- 字体设置 ---
FONT_PATH = "font.ttf"
try:
    font_huge = ImageFont.truetype(FONT_PATH, 65)
    font_title = ImageFont.truetype(FONT_PATH, 24)
    font_item = ImageFont.truetype(FONT_PATH, 18)
    font_small = ImageFont.truetype(FONT_PATH, 14)
    font_tiny = ImageFont.truetype(FONT_PATH, 11)
    font_48 = ImageFont.truetype(FONT_PATH, 48)
    font_36 = ImageFont.truetype(FONT_PATH, 36)
except:
    print("❌ 错误: 找不到 font.ttf")
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
        # 提取湿度数字（去掉百分号）
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

def push_image(img, page_id):
    if str(page_id) not in ENABLED_PAGES:
        print(f"⏩ Page {page_id} 未启用，跳过推送。")
        return
        
    img.save(f"page_{page_id}.png")
    api_headers = {"X-API-Key": API_KEY}
    files = {"images": (f"page_{page_id}.png", open(f"page_{page_id}.png", "rb"), "image/png")}
    data = {"dither": "true", "pageId": str(page_id)}
    try:
        res = requests.post(PUSH_URL, headers=api_headers, files=files, data=data)
        print(f"✅ Page {page_id} 推送成功: {res.status_code}")
    except Exception as e:
        print(f"❌ Page {page_id} 推送失败: {e}")

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

# --- 获取数据的逻辑 (支持切换源) ---
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
            # GitHub 今日最热门仓库（近7天星标最多）
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


# --- 任务：热搜看板 ---
def task_hotlist():
    if "1" not in ENABLED_PAGES and "2" not in ENABLED_PAGES:
        return
        
    source_map = {"zhihu": "知乎热榜", "bilibili": "B站热搜", "github": "GitHub 热门"}
    titles = get_hotlist_data(HOTLIST_SOURCE)
    title_display = source_map.get(HOTLIST_SOURCE, "热门看板")

    # 🌟 核心优化：按像素真实宽度计算换行，解决中英文混排留白问题
    def wrap_text_by_pixels(draw, text, font, max_width):
        lines = []
        current_line = ""
        for char in text:
            test_line = current_line + char
            # 测量加上这个字符后的真实像素宽度
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
        item_gap = 12       # 条目间距
        line_height = 23    # 18号字的行高
        
        for i in range(start_idx, len(items)):
            # 屏幕总宽400，文字从X=45开始，右边留白15，所以最大像素宽度是 340
            lines = wrap_text_by_pixels(draw, items[i], font_item, max_width=340) 
            
            required_h = len(lines) * line_height
            if y + required_h > 295: 
                break
            
            current_num = i + 1
            
            # 左侧黑底数字序号框 (适配 18 号字)
            draw.rounded_rectangle([(10, y), (36, y+24)], radius=6, fill=0)
            num_x = 18 if current