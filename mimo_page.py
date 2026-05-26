import os
import sys
import requests
import re
import math
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont

# =====================================================================
# ⚙️ 配置区（默认地址设定）
# =====================================================================
ADDR_HOME = "常州市新北区书香世家花园"
ADDR_SCHOOL = "常州市田家炳高级中学"

ADCODE_TIANNING = "320402"  # 天宁区（学校所在地）
ADCODE_XINBEI = "320411"   # 新北区（家庭所在地）

API_KEY = os.environ.get("ZECTRIX_API_KEY")
AMAP_KEY = os.environ.get("AMAP_WEATHER_KEY")
# 🌟 多设备支持：从单个 Secret 中读取逗号分隔的多个 MAC 地址，彻底解决泄露风险
ENV_MAC = os.environ.get("ZECTRIX_MAC", "")

# 按逗号拆分、去除两端空格、过滤空值并去重
raw_mac_list = ENV_MAC.split(',')
TARGET_DEVICES = list(set([m.strip() for m in raw_mac_list if m and m.strip()]))

FONT_PATH = "font.ttf"
try:
    font_title = ImageFont.truetype(FONT_PATH, 22)  # 标题与正文共用大字体
    font_small = ImageFont.truetype(FONT_PATH, 13)
except:
    print("❌ 错误: 找不到 font.ttf，请确保仓库中存在该字体文件")
    sys.exit(1)

# =====================================================================
# 🛠️ 核心工具函数组
# =====================================================================

def get_todo_data():
    """从 Zectrix 云端获取全量日程列表"""
    if not API_KEY:
        return []
    try:
        url = "https://cloud.zectrix.com/open/v1/todos"
        headers = {"X-API-Key": API_KEY}
        res = requests.get(url, headers=headers, timeout=10).json()
        if isinstance(res, list):
            return res
        if isinstance(res, dict):
            return res.get("data", []) or res.get("todos", [])
    except Exception as e:
        print(f"❌ 获取云端日程异常: {e}")
    return []

def check_holiday_api(date_str):
    """通过 Timor API 判定法定节假日状态"""
    try:
        url = f"http://timor.tech/api/holiday/info/{date_str}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
        if res.get("code") == 0:
            type_info = res.get("type", {}).get("type")
            return type_info in [1, 2]
    except Exception as e:
        print(f"⚠️ Timor 节假日接口调用失败，启用本地星期兜底: {e}")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.weekday() >= 5
    except:
        return False

def get_coordinates(address, key):
    """高德地理编码获取经纬度"""
    try:
        url = f"https://restapi.amap.com/v3/geocode/geo?address={address}&city=常州&key={key}"
        res = requests.get(url, timeout=5).json()
        if res.get("status") == "1" and res.get("geocodes"):
            return res["geocodes"][0]["location"]
    except Exception as e:
        print(f"❌ 地理编码失败 [{address}]: {e}")
    return None

def get_traffic_info(origin_name, dest_name, key):
    """高德路径规划获取实时通勤路况"""
    if not key:
        return "未配置高德Key，路况不可用。"
    o_coor = get_coordinates(origin_name, key)
    d_coor = get_coordinates(dest_name, key)
    if not o_coor or not d_coor:
        return "地址解析失败。"
    try:
        url = f"https://restapi.amap.com/v3/direction/driving?origin={o_coor}&destination={d_coor}&key={key}&extensions=all"
        res = requests.get(url, timeout=7).json()
        if res.get("status") == "1" and res.get("route"):
            path = res["route"]["paths"][0]
            distance_km = round(int(path["distance"]) / 1000, 1)
            duration_min = round(int(path["duration"]) / 60)
            info_status = path.get("info", "畅通")
            return f"驾车{distance_km}km, 耗时{duration_min}分({info_status})"
    except Exception as e:
        print(f"❌ 路径规划请求异常: {e}")
    return "路况数据刷新超时。"

def get_hybrid_weather(adcode):
    """获取指定区域的天气基础数据"""
    result = {"weather": "未知", "temp_curr": 22, "temp_low": 15, "temp_high": 28, "humidity": "50%"}
    if not AMAP_KEY:
        return result
    try:
        base_url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={adcode}&key={AMAP_KEY}&extensions=base"
        base_resp = requests.get(base_url, timeout=5).json()
        if base_resp.get("status") == "1" and base_resp.get("lives"):
            live = base_resp["lives"][0]
            result["weather"] = live.get("weather", "未知")
            result["temp_curr"] = int(live.get("temperature", 22))
            result["humidity"] = live.get("humidity", "50") + "%"
                
        all_url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={adcode}&key={AMAP_KEY}&extensions=all"
        all_resp = requests.get(all_url, timeout=5).json()
        if all_resp.get("status") == "1" and all_resp.get("forecasts"):
            casts = all_resp["forecasts"][0].get("casts", [])
            if casts:
                result["temp_low"] = int(casts[0].get("nighttemp", 15))
                result["temp_high"] = int(casts[0].get("daytemp", 28))
    except Exception as e:
        print(f"❌ 获取高德天气异常: {e}")
    return result

# =====================================================================
# 🤖 Xiaomi MiMo 大模型接入
# =====================================================================
def call_mimo_llm(prompt_content):
    mimo_key = os.environ.get("MIMO_API_KEY")
    mimo_url = "https://api.xiaomimimo.com/v1/chat/completions"
    mimo_model = "mimo-v2.5"
    
    if not mimo_key:
        print("⚠️ 未检测到真实 MIMO_API_KEY，切换至本地原始数据渲染")
        return prompt_content
    
    mimo_key_clean = mimo_key.strip()
    mask_key = f"{mimo_key_clean[:4]}***{mimo_key_clean[-4:]}" if len(mimo_key_clean) > 8 else "不可用密钥"
    print(f"🔑 [Key安全探针] 原始长度: {len(mimo_key)} -> 清洗后长度: {len(mimo_key_clean)} | 密钥结构预览: {mask_key}")
        
    headers = {
        "Authorization": f"Bearer {mimo_key_clean}", 
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    payload = {
        "model": mimo_model,
        "messages": [
            {
                "role": "system", 
                "content": "你是一个极其贴心的智能出行秘书。请将提供的位置、天气、温湿度、日程、路况等原始数据，智能加工整合成一份适合在400x300像素墨水屏上展示的纯文本日报。字数必须极其精炼（130字以内），不要包含Markdown格式（严禁使用**加粗**或代码块），必须多用换行符换行，每行以简洁恰当的表情符号（如☀️, 👕, 🚗, 📅）开头。你需要根据我给出的温度和湿度，智能为我构思一句精准实用的穿衣/备衣建议融入日报中。直接输出最终排版文本。"
            },
            {"role": "user", "content": prompt_content}
        ],
        "temperature": 0.4
    }
    try:
        print(f"📡 正在发起大模型请求 URL: {mimo_url} | 模型: {mimo_model}")
        response = requests.post(mimo_url, headers=headers, json=payload, timeout=20)
        print(f"📥 大模型网关响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            res = response.json()
            if "choices" in res:
                return res["choices"][0]["message"]["content"].strip()
            else:
                print(f"❌ 大模型返回格式异常")
                raise Exception("Format Error")
        else:
            print(f"❌ 接口请求未通过网关，错误预览: {response.text[:180]}")
            raise Exception(f"HTTP_STATUS_{response.status_code}")
            
    except Exception as e:
        print(f"❌ MiMo 大模型调用流程捕获异常: {e}")
        return f"⚠️ 智整失败(AI接口异常)\n{prompt_content}"

# =====================================================================
# 🎨 图像像素级安全排版渲染与推送
# =====================================================================
def wrap_text_by_pixels(draw, text, font, max_width=360):
    lines = []
    current_line = ""
    for char in text:
        if char == '\n':
            lines.append(current_line)
            current_line = ""
            continue
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

def push_page_5(final_text, title_tag):
    img = Image.new('1', (400, 300), color=255)
    draw = ImageDraw.Draw(img)
    
    draw.rounded_rectangle([(10, 10), (390, 45)], radius=6, fill=0)
    draw.text((20, 16), title_tag, font=font_title, fill=255)
    
    # 核心：使用 font_title 渲染内容，max_width 保持 365 像素
    lines = wrap_text_by_pixels(draw, final_text, font_title, max_width=365)
    y_cursor = 60
    
    # 字号增大后，行距调整为 28px，最大容纳约 8 行
    for line in lines[:8]:  
        draw.text((15, y_cursor), line, font=font_title, fill=0)
        y_cursor += 28

    img_path = "page_5.png"
    img.save(img_path)
    if not API_KEY:
        print("⏩ 未配置 ZECTRIX_API_KEY，本地图片保存成功。")
        return
        
    api_headers = {"X-API-Key": API_KEY}
    data = {"dither": "true", "pageId": "5"}
    for mac in TARGET_DEVICES:
        url = f"https://cloud.zectrix.com/open/v1/devices/{mac}/display/image"
        try:
            with open(img_path, "rb") as f:
                res = requests.post(url, headers=api_headers, files={"images": (img_path, f, "image/png")}, data=data)
                print(f"✅ 设备 [{mac}] Page 5 推送响应: {res.status_code}")
        except Exception as e:
            print(f"❌ 设备 [{mac}] Page 5 推送异常: {e}")

# =====================================================================
# ⚙️ 核心业务决策树
# =====================================================================
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    
    now_bj = datetime.utcnow() + timedelta(hours=8)
    today_str = now_bj.strftime("%Y-%m-%d")
    tomorrow_str = (now_bj + timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_str = (now_bj - timedelta(days=1)).strftime("%Y-%m-%d")
    
    if not mode:
        mode = "morning" if now_bj.hour < 12 else "evening"
        
    print(f"⏰ 当前北京时间: {now_bj.strftime('%Y-%m-%d %H:%M:%S')} | 运行模式: {mode}")
    
    all_todos = get_todo_data()
    todos_today = [t for t in all_todos if t.get("dueDate") == today_str]
    todos_tomorrow = [t for t in all_todos if t.get("dueDate") == tomorrow_str]
    todos_yesterday = [t for t in all_todos if t.get("dueDate") == yesterday_str]
    
    duty_today = any("住校值班" in str(t.get("title", "")) for t in todos_today)
    duty_yesterday = any("住校值班" in str(t.get("title", "")) for t in todos_yesterday)
    
    work_keywords = ["高一物理", "高二物理", "晚辅导", "晚辅导1", "晚辅导2"]
    
    if mode == "morning":
        is_holiday = check_holiday_api(today_str) or (len(todos_today) == 0)
        has_work_context = any(any(kw in str(t.get("title", "")) for kw in work_keywords) for t in todos_today)
        
        skip_traffic = duty_yesterday or (is_holiday and not has_work_context)
        target_adcode = ADCODE_XINBEI if (is_holiday and not has_work_context) else ADCODE_TIANNING
        
        weather = get_hybrid_weather(target_adcode)
        traffic_str = "今日豁免路况" if skip_traffic else get_traffic_info(ADDR_HOME, ADDR_SCHOOL, AMAP_KEY)
        todo_str = "、".join([t.get("title", "") for t in todos_today]) if todos_today else "暂无计划"
        
        # 💡 [数据整包灌注]：不提供现成逻辑建议，将温湿度原始指标交给 AI 自行判断
        raw_prompt = (
            f"位置：{'书香世家' if target_adcode==ADCODE_XINBEI else '田家炳高级中学'}\n"
            f"实时天气：{weather['weather']}\n"
            f"当前温度：{weather['temp_curr']}°C\n"
            f"全天气温：{weather['temp_low']}°C ~ {weather['temp_high']}°C\n"
            f"相对湿度：{weather['humidity']}\n"
            f"今日日程：{todo_str}\n"
            f"通勤路况：{traffic_str}"
        )
        
        print("💡 正在提交 MiMo 模型智能构建晨报(含动态穿衣策略)...")
        final_report = call_mimo_llm(raw_prompt)
        push_page_5(final_report, f"◆ 晨间智能早报 ({now_bj.strftime('%H:%M')})")
        
    elif mode == "evening":
        is_tomorrow_holiday = check_holiday_api(tomorrow_str) or (len(todos_tomorrow) == 0)
        has_tomorrow_work = any(any(kw in str(t.get("title", "")) for kw in work_keywords) for t in todos_tomorrow)
        
        skip_traffic = duty_today or ( (check_holiday_api(today_str) or len(todos_today)==0) and not any(any(kw in str(t.get("title", "")) for kw in work_keywords) for t in todos_today) )
        tomorrow_adcode = ADCODE_XINBEI if (is_tomorrow_holiday and not has_tomorrow_work) else ADCODE_TIANNING
        
        weather_tomorrow = get_hybrid_weather(tomorrow_adcode)
        traffic_str = "假期或留校豁免路况" if skip_traffic else get_traffic_info(ADDR_SCHOOL, ADDR_HOME, AMAP_KEY)
        todo_str = "、".join([t.get("title", "") for t in todos_tomorrow]) if todos_tomorrow else "明日暂无安排"
        
        # 💡 [数据整包灌注]：同上，将明日指标喂给 AI 自行产生备衣策略
        raw_prompt = (
            f"明日位置：{'书香世家' if tomorrow_adcode==ADCODE_XINBEI else '田家炳高级中学'}\n"
            f"明日天气：{weather_tomorrow['weather']}\n"
            f"温度区间：{weather_tomorrow['temp_low']}°C ~ {weather_tomorrow['temp_high']}°C\n"
            f"空气湿度：{weather_tomorrow['humidity']}\n"
            f"明日日程：{todo_str}\n"
            f"今晚路况：{traffic_str}"
        )
        
        print("💡 正在提交 MiMo 模型智能构建晚报(含动态备衣策略)...")
        final_report = call_mimo_llm(raw_prompt)
        push_page_5(final_report, f"◆ 晚间贴心筑梦 ({now_bj.strftime('%H:%M')})")

if __name__ == "__main__":
    main()
