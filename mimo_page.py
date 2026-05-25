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
ENV_MAC = os.environ.get("ZECTRIX_MAC")

MAC_ADDRESSES = [ENV_MAC] if ENV_MAC else []
MAC_ADDRESSES.append("DC:B4:D9:19:1C:F0")
TARGET_DEVICES = list(set([m.strip() for m in MAC_ADDRESSES if m and m.strip()]))

FONT_PATH = "font.ttf"
try:
    font_title = ImageFont.truetype(FONT_PATH, 22)
    font_item = ImageFont.truetype(FONT_PATH, 15) 
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
            return f"驾车{distance_km}km, 耗时约{duration_min}分钟 ({info_status})"
    except Exception as e:
        print(f"❌ 路径规划请求异常: {e}")
    return "路况数据刷新超时。"

def get_hybrid_weather(adcode):
    """获取指定区域的天气基础数据"""
    result = {"weather": "未知", "temp_curr": 22, "temp_low": 15, "temp_high": 28, "humidity": "50%", "feel_temp": "22°C"}
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
            
            try:
                t, h = result["temp_curr"], int(live.get("humidity", 50))
                e = (h / 100.0) * 6.105 * math.exp((17.27 * t) / (237.7 + t))
                result["feel_temp"] = f"{round(t + 0.33 * e - 4.0, 1)}°C"
            except:
                result["feel_temp"] = f"{result['temp_curr']}°C"
                
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

def get_clothing_advice(temp, humidity_str):
    try:
        t = int(temp)
        h = int(humidity_str.replace('%', ''))
        if t >= 28: return "闷热，穿透气短袖。" if h >= 70 else "炎热，穿薄短袖防晒。"
        elif t >= 22: return "湿热，穿宽松T恤。" if h >= 70 else "舒适，穿长短袖T恤皆可。"
        elif t >= 16: return "偏凉，穿长袖加外套。" if h >= 70 else "清凉，穿长袖衬衫或卫衣。"
        elif t >= 10: return "湿冷，建议穿厚夹克。" if h >= 70 else "偏冷，穿风衣或毛衣。"
        else: return "寒冷，建议着厚羽绒服。"
    except:
        return "依据实时体感温度调整着装。"

# =====================================================================
# 🤖 Xiaomi MiMo 大模型接入
# =====================================================================
def call_mimo_llm(prompt_content):
    mimo_key = os.environ.get("MIMO_API_KEY")
    mimo_url = "https://api.xiaomimimo.com/v1/chat/completions"
    mimo_model = "mimo-v2.5"
    
    if not mimo_key:
        print("⚠️ 未检测到真实 MIMO_API_KEY，切换至本地原始数据渲染")
        clean_prompt = prompt_content.replace("【晨报数据】\n", "").replace("【晚报数据】\n", "")
        return f"⚠️ 缺少大模型配置，显示原始简报：\n{clean_prompt}"
        
    # 💡 [针对 403 优化]: 加入高级浏览器 User-Agent 头，将脚本请求伪装成标准 Chrome 访问，防止防火墙策略误拦截
    headers = {
        "Authorization": f"Bearer {mimo_key}", 
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    payload = {
        "model": mimo_model,
        "messages": [
            {
                "role": "system", 
                "content": "你是一个贴心的智能精简助手。请将提供的数据整理成一份适合在400x300像素墨水屏上展示的纯文本日报。字数必须极其精炼（150字以内），不要包含Markdown格式（如**加粗**或代码块），多用换行符，多用简洁的表情符号符号开端。直接输出最终排版文本。"
            },
            {"role": "user", "content": prompt_content}
        ],
        "temperature": 0.3
    }
    try:
        print(f"📡 正在发起大模型请求 URL: {mimo_url} | 模型: {mimo_model}")
        response = requests.post(mimo_url, headers=headers, json=payload, timeout=20)
        print(f"📥 大模型响应状态码: {response.status_code}")
        
        # 💡 [关键防御]: 先验证状态码。只有当状态码为 200 成功时才去解析 JSON，绝不盲目调用导致程序闪退
        if response.status_code == 200:
            res = response.json()
            if "choices" in res:
                return res["choices"][0]["message"]["content"].strip()
            else:
                print(f"❌ 大模型返回格式异常，未找到 choices 键: {res}")
                raise Exception("Format Error")
        else:
            # 打印服务器返回的前 200 个非 JSON 字符，方便我们在 Actions 里抓取真正的报错网页源码
            print(f"❌ 接口请求未通过，错误预览: {response.text[:200]}")
            raise Exception(f"HTTP_STATUS_{response.status_code}")
            
    except Exception as e:
        print(f"❌ MiMo 大模型调用流程捕获异常: {e}")
        # 如果大模型因403被防火墙干掉，立刻优雅解析高德数据填充到墨水屏中，不留下白屏遗憾
        clean_prompt = prompt_content.replace("【晨报数据】\n", "").replace("【晚报数据】\n", "")
        return f"⚠️ 智整失败(AI接口异常)\n📊 原始简报如下:\n{clean_prompt}"

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
    
    # 顶部黑底白字通知栏
    draw.rounded_rectangle([(10, 10), (390, 45)], radius=6, fill=0)
    draw.text((20, 16), title_tag, font=font_title, fill=255)
    
    # 动态折行文本渲染
    lines = wrap_text_by_pixels(draw, final_text, font_item, max_width=370)
    y_cursor = 60
    for line in lines[:11]:  # 增加行数容纳能力
        draw.text((15, y_cursor), line, font=font_item, fill=0)
        y_cursor += 21

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
        advice = get_clothing_advice(weather["temp_curr"], weather["humidity"])
        
        traffic_str = "今日豁免路况提醒。" if skip_traffic else get_traffic_info(ADDR_HOME, ADDR_SCHOOL, AMAP_KEY)
        todo_str = "、".join([t.get("title", "") for t in todos_today]) if todos_today else "今日暂无计划"
        
        raw_prompt = (
            f"【晨报数据】\n"
            f"天气：{'新北主家' if target_adcode==ADCODE_XINBEI else '天宁校区'}·{weather['weather']} {weather['temp_curr']}°C({weather['temp_low']}°~{weather['temp_high']}°)\n"
            f"建议：{advice}\n"
            f"日程：{todo_str}\n"
            f"路况：{traffic_str}"
        )
        
        print("💡 正在提交 MiMo 模型构建晨报...")
        final_report = call_mimo_llm(raw_prompt)
        push_page_5(final_report, f"◆ 晨间智能早报 ({now_bj.strftime('%H:%M')})")
        
    elif mode == "evening":
        is_tomorrow_holiday = check_holiday_api(tomorrow_str) or (len(todos_tomorrow) == 0)
        has_tomorrow_work = any(any(kw in str(t.get("title", "")) for kw in work_keywords) for t in todos_tomorrow)
        
        skip_traffic = duty_today or ( (check_holiday_api(today_str) or len(todos_today)==0) and not any(any(kw in str(t.get("title", "")) for kw in work_keywords) for t in todos_today) )
        tomorrow_adcode = ADCODE_XINBEI if (is_tomorrow_holiday and not has_tomorrow_work) else ADCODE_TIANNING
        
        weather_tomorrow = get_hybrid_weather(tomorrow_adcode)
        advice_tomorrow = get_clothing_advice(weather_tomorrow["temp_low"], weather_tomorrow["humidity"])
        
        traffic_str = "今晚校内值班或假期豁免路况。" if skip_traffic else get_traffic_info(ADDR_SCHOOL, ADDR_HOME, AMAP_KEY)
        todo_str = "..".join([t.get("title", "") for t in todos_tomorrow]) if todos_tomorrow else "明日暂无特殊安排"
        
        raw_prompt = (
            f"【晚报数据】\n"
            f"明日天气：{'新北主家' if tomorrow_adcode==ADCODE_XINBEI else '天宁校区'}·{weather_tomorrow['weather']} {weather_tomorrow['temp_low']}°~{weather_tomorrow['temp_high']}°\n"
            f"备衣：{advice_tomorrow}\n"
            f"明日日程：{todo_str}\n"
            f"今晚路况：{traffic_str}"
        )
        
        print("💡 正在提交 MiMo 模型构建晚报...")
        final_report = call_mimo_llm(raw_prompt)
        push_page_5(final_report, f"◆ 晚间贴心筑梦 ({now_bj.strftime('%H:%M')})")

if __name__ == "__main__":
    main()
