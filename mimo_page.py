{\rtf1\ansi\ansicpg936\cocoartf2870
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import os\
import sys\
import requests\
import re\
import math\
from datetime import datetime, timedelta\
from PIL import Image, ImageDraw, ImageFont\
\
# =====================================================================\
# \uc0\u9881 \u65039  \u37197 \u32622 \u21306 \u65288 \u40664 \u35748 \u22320 \u22336 \u35774 \u23450 \u65289 \
# =====================================================================\
# \uc0\u40664 \u35748 \u26657 \u21306 /\u23478 \u24237 \u22320 \u22336 \u25991 \u26412 \u65292 \u29992 \u20110 \u39640 \u24503 \u36335 \u24452 \u35268 \u21010 \
ADDR_HOME = "\uc0\u24120 \u24030 \u24066 \u26032 \u21271 \u21306 \u20070 \u39321 \u19990 \u23478 \u33457 \u22253 "\
ADDR_SCHOOL = "\uc0\u24120 \u24030 \u24066 \u30000 \u23478 \u28851 \u39640 \u32423 \u20013 \u23398 "\
\
# \uc0\u40664 \u35748 \u39640 \u24503 \u22478 \u24066  adcode\
ADCODE_TIANNING = "320402"  # \uc0\u22825 \u23425 \u21306 \u65288 \u23398 \u26657 \u25152 \u22312 \u22320 \u65289 \
ADCODE_XINBEI = "320411"   # \uc0\u26032 \u21271 \u21306 \u65288 \u23478 \u24237 \u25152 \u22312 \u22320 \u65289 \
\
# \uc0\u22522 \u30784 \u29615 \u22659 \u21464 \u37327 \u33719 \u21462 \
API_KEY = os.environ.get("ZECTRIX_API_KEY")\
AMAP_KEY = os.environ.get("AMAP_WEATHER_KEY")\
ENV_MAC = os.environ.get("ZECTRIX_MAC")\
\
MAC_ADDRESSES = [ENV_MAC] if ENV_MAC else []\
MAC_ADDRESSES.append("DC:B4:D9:19:1C:F0")\
TARGET_DEVICES = list(set([m.strip() for m in MAC_ADDRESSES if m and m.strip()]))\
\
# --- \uc0\u23383 \u20307 \u21021 \u22987 \u21270  ---\
FONT_PATH = "font.ttf"\
try:\
    font_title = ImageFont.truetype(FONT_PATH, 22)\
    font_item = ImageFont.truetype(FONT_PATH, 16)\
    font_small = ImageFont.truetype(FONT_PATH, 13)\
except:\
    print("\uc0\u10060  \u38169 \u35823 : \u25214 \u19981 \u21040  font.ttf\u65292 \u35831 \u30830 \u20445 \u20179 \u24211 \u20013 \u23384 \u22312 \u35813 \u23383 \u20307 \u25991 \u20214 ")\
    sys.exit(1)\
\
# =====================================================================\
# \uc0\u55357 \u57056 \u65039  \u26680 \u24515 \u24037 \u20855 \u20989 \u25968 \u32452 \
# =====================================================================\
\
def get_todo_data():\
    """\uc0\u20174  Zectrix \u20113 \u31471 \u33719 \u21462 \u20840 \u37327 \u26085 \u31243 \u21015 \u34920 """\
    if not API_KEY:\
        return []\
    try:\
        url = "https://cloud.zectrix.com/open/v1/todos"\
        headers = \{"X-API-Key": API_KEY\}\
        res = requests.get(url, headers=headers, timeout=10).json()\
        if isinstance(res, list):\
            return res\
        if isinstance(res, dict):\
            return res.get("data", []) or res.get("todos", [])\
    except Exception as e:\
        print(f"\uc0\u10060  \u33719 \u21462 \u20113 \u31471 \u26085 \u31243 \u24322 \u24120 : \{e\}")\
    return []\
\
def check_holiday_api(date_str):\
    """\uc0\u36890 \u36807  Timor API \u21028 \u23450 \u27861 \u23450 \u33410 \u20551 \u26085 \u29366 \u24577  (0\u24037 \u20316 \u26085 , 1\u21608 \u26411 , 2\u33410 \u26085 , 3\u35843 \u20241 \u29677 )"""\
    try:\
        url = f"http://timor.tech/api/holiday/info/\{date_str\}"\
        res = requests.get(url, headers=\{'User-Agent': 'Mozilla/5.0'\}, timeout=5).json()\
        if res.get("code") == 0:\
            type_info = res.get("type", \{\}).get("type")\
            return type_info in [1, 2]  # \uc0\u21608 \u26411 \u25110 \u27861 \u23450 \u33410 \u20551 \u26085 \u36820 \u22238  True\
    except Exception as e:\
        print(f"\uc0\u9888 \u65039  Timor \u33410 \u20551 \u26085 \u25509 \u21475 \u35843 \u29992 \u22833 \u36133 \u65292 \u21551 \u29992 \u26412 \u22320 \u26143 \u26399 \u20828 \u24213 : \{e\}")\
    # \uc0\u20828 \u24213 \u65306 \u25353 \u26143 \u26399 \u20845 \u12289 \u26143 \u26399 \u26085 \u21028 \u26029 \
    try:\
        dt = datetime.strptime(date_str, "%Y-%m-%d")\
        return dt.weekday() >= 5\
    except:\
        return False\
\
def get_coordinates(address, key):\
    """\uc0\u39640 \u24503 \u22320 \u29702 \u32534 \u30721 \u33719 \u21462 \u32463 \u32428 \u24230 """\
    try:\
        url = f"https://restapi.amap.com/v3/geocode/geo?address=\{address\}&city=\uc0\u24120 \u24030 &key=\{key\}"\
        res = requests.get(url, timeout=5).json()\
        if res.get("status") == "1" and res.get("geocodes"):\
            return res["geocodes"][0]["location"]\
    except Exception as e:\
        print(f"\uc0\u10060  \u22320 \u29702 \u32534 \u30721 \u22833 \u36133  [\{address\}]: \{e\}")\
    return None\
\
def get_traffic_info(origin_name, dest_name, key):\
    """\uc0\u39640 \u24503 \u36335 \u24452 \u35268 \u21010 \u33719 \u21462 \u23454 \u26102 \u36890 \u21220 \u36335 \u20917 """\
    if not key:\
        return "\uc0\u26410 \u37197 \u32622 \u39640 \u24503 Key\u65292 \u26080 \u27861 \u33719 \u21462 \u36335 \u20917 \u12290 "\
    o_coor = get_coordinates(origin_name, key)\
    d_coor = get_coordinates(dest_name, key)\
    if not o_coor or not d_coor:\
        return "\uc0\u26080 \u27861 \u35299 \u26512 \u22320 \u22336 \u22352 \u26631 \u65292 \u36335 \u20917 \u26242 \u26102 \u19981 \u21487 \u29992 \u12290 "\
    try:\
        url = f"https://restapi.amap.com/v3/direction/driving?origin=\{o_coor\}&destination=\{d_coor\}&key=\{key\}&extensions=all"\
        res = requests.get(url, timeout=7).json()\
        if res.get("status") == "1" and res.get("route"):\
            path = res["route"]["paths"][0]\
            distance_km = round(int(path["distance"]) / 1000, 1)\
            duration_min = round(int(path["duration"]) / 60)\
            info_status = path.get("info", "\uc0\u30021 \u36890 ")\
            return f"\uc0\u20174  \{origin_name.split('\u21306 ')[-1]\} \u21040  \{dest_name.split('\u21306 ')[-1]\}\u65292 \u20840 \u31243  \{distance_km\}\u20844 \u37324 \u65292 \u24403 \u21069 \u39550 \u36710 \u39044 \u35745 \u32791 \u26102  \{duration_min\}\u20998 \u38047  (\{info_status\})\u12290 "\
    except Exception as e:\
        print(f"\uc0\u10060  \u36335 \u24452 \u35268 \u21010 \u35831 \u27714 \u24322 \u24120 : \{e\}")\
    return "\uc0\u36335 \u20917 \u25968 \u25454 \u21047 \u26032 \u36229 \u26102 \u12290 "\
\
def get_hybrid_weather(adcode):\
    """\uc0\u33719 \u21462 \u25351 \u23450 \u21306 \u22495 \u30340 \u22825 \u27668 \u22522 \u30784 \u25968 \u25454 """\
    result = \{"weather": "\uc0\u26410 \u30693 ", "temp_curr": 22, "temp_low": 15, "temp_high": 28, "humidity": "50%", "feel_temp": "22\'b0C"\}\
    if not AMAP_KEY:\
        return result\
    try:\
        base_url = f"https://restapi.amap.com/v3/weather/weatherInfo?city=\{adcode\}&key=\{AMAP_KEY\}&extensions=base"\
        base_resp = requests.get(base_url, timeout=5).json()\
        if base_resp.get("status") == "1" and base_resp.get("lives"):\
            live = base_resp["lives"][0]\
            result["weather"] = live.get("weather", "\uc0\u26410 \u30693 ")\
            result["temp_curr"] = int(live.get("temperature", 22))\
            result["humidity"] = live.get("humidity", "50") + "%"\
            \
            # \uc0\u31616 \u26131 \u20307 \u24863 \u28201 \u24230 \u20272 \u31639 \
            try:\
                t, h = result["temp_curr"], int(live.get("humidity", 50))\
                e = (h / 100.0) * 6.105 * math.exp((17.27 * t) / (237.7 + t))\
                result["feel_temp"] = f"\{round(t + 0.33 * e - 4.0, 1)\}\'b0C"\
            except:\
                result["feel_temp"] = f"\{result['temp_curr']\}\'b0C"\
                \
        all_url = f"https://restapi.amap.com/v3/weather/weatherInfo?city=\{adcode\}&key=\{AMAP_KEY\}&extensions=all"\
        all_resp = requests.get(all_url, timeout=5).json()\
        if all_resp.get("status") == "1" and all_resp.get("forecasts"):\
            casts = all_resp["forecasts"][0].get("casts", [])\
            if casts:\
                result["temp_low"] = int(casts[0].get("nighttemp", 15))\
                result["temp_high"] = int(casts[0].get("daytemp", 28))\
    except Exception as e:\
        print(f"\uc0\u10060  \u33719 \u21462 \u39640 \u24503 \u22825 \u27668 \u24322 \u24120 : \{e\}")\
    return result\
\
def get_clothing_advice(temp, humidity_str):\
    try:\
        t = int(temp)\
        h = int(humidity_str.replace('%', ''))\
        if t >= 28: return "\uc0\u38391 \u28909 \u65292 \u31359 \u36879 \u27668 \u30701 \u34966 \u12290 " if h >= 70 else "\u28814 \u28909 \u65292 \u31359 \u34180 \u30701 \u34966 \u38450 \u26194 \u12290 "\
        elif t >= 22: return "\uc0\u28287 \u28909 \u65292 \u31359 \u23485 \u26494 T\u24676 \u12290 " if h >= 70 else "\u33298 \u36866 \u65292 \u31359 \u38271 \u30701 \u34966 T\u24676 \u30342 \u21487 \u12290 "\
        elif t >= 16: return "\uc0\u20559 \u20937 \u65292 \u31359 \u38271 \u34966 \u21152 \u22806 \u22871 \u12290 " if h >= 70 else "\u28165 \u20937 \u65292 \u31359 \u38271 \u34966 \u34924 \u34923 \u25110 \u21355 \u34915 \u12290 "\
        elif t >= 10: return "\uc0\u28287 \u20919 \u65292 \u24314 \u35758 \u31359 \u21402 \u22841 \u20811 \u12290 " if h >= 70 else "\u20559 \u20919 \u65292 \u31359 \u39118 \u34915 \u25110 \u27611 \u34915 \u12290 "\
        else: return "\uc0\u23506 \u20919 \u65292 \u24314 \u35758 \u30528 \u21402 \u32701 \u32466 \u26381 \u12290 "\
    except:\
        return "\uc0\u20381 \u25454 \u23454 \u26102 \u20307 \u24863 \u28201 \u24230 \u35843 \u25972 \u30528 \u35013 \u12290 "\
\
# =====================================================================\
# \uc0\u55358 \u56598  Xiaomi MiMo \u22823 \u27169 \u22411 \u25509 \u20837 \
# =====================================================================\
def call_mimo_llm(prompt_content):\
    mimo_key = os.environ.get("MIMO_API_KEY")\
    mimo_url = os.environ.get("MIMO_API_URL", "https://platform.xiaomimimo.com/v1/chat/completions")\
    mimo_model = os.environ.get("MIMO_MODEL", "mimo-v2.5")\
    \
    if not mimo_key:\
        print("\uc0\u9888 \u65039  \u26410 \u37197 \u32622  MIMO_API_KEY\u65292 \u36820 \u22238 \u26412 \u22320 \u21407 \u22987 \u27169 \u26495 ")\
        return prompt_content[:150]\
        \
    headers = \{"Authorization": f"Bearer \{mimo_key\}", "Content-Type": "application/json"\}\
    payload = \{\
        "model": mimo_model,\
        "messages": [\
            \{\
                "role": "system", \
                "content": "\uc0\u20320 \u26159 \u19968 \u20010 \u36148 \u24515 \u30340 \u26234 \u33021 \u31934 \u31616 \u21161 \u25163 \u12290 \u35831 \u23558 \u25552 \u20379 \u30340 \u25968 \u25454 \u25972 \u29702 \u25104 \u19968 \u20221 \u36866 \u21512 \u22312 400x300\u20687 \u32032 \u22696 \u27700 \u23631 \u19978 \u23637 \u31034 \u30340 \u32431 \u25991 \u26412 \u26085 \u25253 \u12290 \u23383 \u25968 \u24517 \u39035 \u26497 \u20854 \u31934 \u28860 \u65288 150\u23383 \u20197 \u20869 \u65289 \u65292 \u19981 \u35201 \u21253 \u21547 Markdown\u26684 \u24335 \u65288 \u22914 **\u21152 \u31895 **\u25110 \u20195 \u30721 \u22359 \u65289 \u65292 \u22810 \u29992 \u25442 \u34892 \u31526 \u65292 \u22810 \u29992 \u31616 \u27905 \u30340 \u34920 \u24773 \u31526 \u21495 \u31526 \u21495 \u24320 \u31471 \u12290 \u30452 \u25509 \u36755 \u20986 \u26368 \u32456 \u25490 \u29256 \u25991 \u26412 \u12290 "\
            \},\
            \{"role": "user", "content": prompt_content\}\
        ],\
        "temperature": 0.3\
    \}\
    try:\
        res = requests.post(mimo_url, headers=headers, json=payload, timeout=20).json()\
        return res["choices"][0]["message"]["content"].strip()\
    except Exception as e:\
        print(f"\uc0\u10060  MiMo \u22823 \u27169 \u22411 \u35843 \u29992 \u22833 \u36133 : \{e\}")\
        return "\uc0\u25968 \u25454 \u25972 \u21512 \u22833 \u36133 \u65292 \u35831 \u38405 \u35835 \u19979 \u23631 \u21407 \u22987 \u31616 \u25253 \u12290 "\
\
# =====================================================================\
# \uc0\u55356 \u57256  \u22270 \u20687 \u20687 \u32032 \u32423 \u23433 \u20840 \u25490 \u29256 \u28210 \u26579 \u19982 \u25512 \u36865 \
# =====================================================================\
def wrap_text_by_pixels(draw, text, font, max_width=360):\
    lines = []\
    current_line = ""\
    for char in text:\
        if char == '\\n':\
            lines.append(current_line)\
            current_line = ""\
            continue\
        test_line = current_line + char\
        try:\
            w = draw.textlength(test_line, font=font)\
        except AttributeError:\
            w = draw.textbbox((0,0), test_line, font=font)[2]\
        if w <= max_width:\
            current_line = test_line\
        else:\
            lines.append(current_line)\
            current_line = char\
    if current_line:\
        lines.append(current_line)\
    return lines\
\
def push_page_5(final_text, title_tag):\
    img = Image.new('1', (400, 300), color=255)\
    draw = ImageDraw.Draw(img)\
    \
    # \uc0\u39030 \u37096 \u27178 \u24133 \
    draw.rounded_rectangle([(10, 10), (390, 45)], radius=6, fill=0)\
    draw.text((20, 16), title_tag, font=font_title, fill=255)\
    \
    # \uc0\u20869 \u23481 \u28210 \u26579 \
    lines = wrap_text_by_pixels(draw, final_text, font_item, max_width=370)\
    y_cursor = 60\
    for line in lines[:10]:  # \uc0\u38480 \u21046 \u26368 \u22823 \u34892 \u25968 \u38450 \u27490 \u28322 \u20986 \u36793 \u30028 \
        draw.text((15, y_cursor), line, font=font_item, fill=0)\
        y_cursor += 22\
\
    # \uc0\u25512 \u36865 \u36923 \u36753 \
    img_path = "page_5.png"\
    img.save(img_path)\
    if not API_KEY:\
        print("\uc0\u9193  \u26410 \u37197 \u32622  ZECTRIX_API_KEY\u65292 \u26412 \u22320 \u22270 \u29255 \u20445 \u23384 \u25104 \u21151 \u12290 ")\
        return\
        \
    api_headers = \{"X-API-Key": API_KEY\}\
    data = \{"dither": "true", "pageId": "5"\}\
    for mac in TARGET_DEVICES:\
        url = f"https://cloud.zectrix.com/open/v1/devices/\{mac\}/display/image"\
        try:\
            with open(img_path, "rb") as f:\
                res = requests.post(url, headers=api_headers, files=\{"images": (img_path, f, "image/png")\}, data=data)\
                print(f"\uc0\u9989  \u35774 \u22791  [\{mac\}] Page 5 \u25512 \u36865 \u21709 \u24212 : \{res.status_code\}")\
        except Exception as e:\
            print(f"\uc0\u10060  \u35774 \u22791  [\{mac\}] Page 5 \u25512 \u36865 \u24322 \u24120 : \{e\}")\
\
# =====================================================================\
# \uc0\u9881 \u65039  \u26680 \u24515 \u19994 \u21153 \u20915 \u31574 \u26641 \
# =====================================================================\
def main():\
    # \uc0\u20801 \u35768 \u36890 \u36807  GitHub Actions \u21442 \u25968 \u20256 \u20837 \u27169 \u24335 \u65292 \u21542 \u21017 \u36890 \u36807 \u24403 \u21069 \u21271 \u20140 \u26102 \u38388 \u33258 \u21160 \u21028 \u26029 \
    mode = sys.argv[1] if len(sys.argv) > 1 else None\
    \
    now_bj = datetime.utcnow() + timedelta(hours=8)\
    today_str = now_bj.strftime("%Y-%m-%d")\
    tomorrow_str = (now_bj + timedelta(days=1)).strftime("%Y-%m-%d")\
    yesterday_str = (now_bj - timedelta(days=1)).strftime("%Y-%m-%d")\
    \
    if not mode:\
        mode = "morning" if now_bj.hour < 12 else "evening"\
        \
    print(f"\uc0\u9200  \u24403 \u21069 \u21271 \u20140 \u26102 \u38388 : \{now_bj.strftime('%Y-%m-%d %H:%M:%S')\} | \u36816 \u34892 \u27169 \u24335 : \{mode\}")\
    \
    # 1. \uc0\u25438 \u21462 \u20113 \u31471 \u20840 \u37327 \u26085 \u31243 \
    all_todos = get_todo_data()\
    todos_today = [t for t in all_todos if t.get("dueDate") == today_str]\
    todos_tomorrow = [t for t in all_todos if t.get("dueDate") == tomorrow_str]\
    todos_yesterday = [t for t in all_todos if t.get("dueDate") == yesterday_str]\
    \
    # 2. \uc0\u20303 \u26657 \u20540 \u29677 \u21028 \u23450 \u26465 \u20214 \
    duty_today = any("\uc0\u20303 \u26657 \u20540 \u29677 " in str(t.get("title", "")) for t in todos_today)\
    duty_yesterday = any("\uc0\u20303 \u26657 \u20540 \u29677 " in str(t.get("title", "")) for t in todos_yesterday)\
    \
    # \uc0\u29305 \u27530 \u25945 \u23398 \u20851 \u38190 \u23383 \
    work_keywords = ["\uc0\u39640 \u19968 \u29289 \u29702 ", "\u39640 \u20108 \u29289 \u29702 ", "\u26202 \u36741 \u23548 ", "\u26202 \u36741 \u23548 1", "\u26202 \u36741 \u23548 2"]\
    \
    if mode == "morning":\
        # --- \uc0\u26216 \u38388 \u26089 \u25253 \u36923 \u36753  (06:30) ---\
        is_holiday = check_holiday_api(today_str) or (len(todos_today) == 0)\
        has_work_context = any(any(kw in str(t.get("title", "")) for kw in work_keywords) for t in todos_today)\
        \
        # \uc0\u21028 \u23450 \u36335 \u20917 \u26159 \u21542 \u34987 \u35905 \u20813 \
        skip_traffic = duty_yesterday or (is_holiday and not has_work_context)\
        # \uc0\u21028 \u23450 \u22825 \u27668 \u21306 \u22495 \
        target_adcode = ADCODE_XINBEI if (is_holiday and not has_work_context) else ADCODE_TIANNING\
        \
        weather = get_hybrid_weather(target_adcode)\
        advice = get_clothing_advice(weather["temp_curr"], weather["humidity"])\
        \
        traffic_str = "\uc0\u20170 \u26085 \u35905 \u20813 \u36335 \u20917 \u25552 \u37266 \u12290 " if skip_traffic else get_traffic_info(ADDR_HOME, ADDR_SCHOOL, AMAP_KEY)\
        todo_str = "\uc0\u12289 ".join([t.get("title", "") for t in todos_today]) if todos_today else "\u20170 \u26085 \u26242 \u26080 \u35745 \u21010 "\
        \
        raw_prompt = (\
            f"\uc0\u12304 \u26216 \u25253 \u25968 \u25454 \u12305 \\n"\
            f"\uc0\u26085 \u26399 \u65306 \{today_str\}\\n"\
            f"\uc0\u27668 \u35937 \u65306 \{'\u26032 \u21271 \u20027 \u23478 ' if target_adcode==ADCODE_XINBEI else '\u22825 \u23425 \u26657 \u21306 '\}\'b7\{weather['weather']\}\u65292 \u24403 \u21069 \{weather['temp_curr']\}\'b0C(\{weather['temp_low']\}\'b0~\{weather['temp_high']\}\'b0)\u65292 \u28287 \u24230 \{weather['humidity']\}\u65292 \u20307 \u24863 \{weather['feel_temp']\}\u12290 \\n"\
            f"\uc0\u30528 \u35013 \u24314 \u35758 \u65306 \{advice\}\\n"\
            f"\uc0\u20170 \u26085 \u26085 \u31243 \u65306 \{todo_str\}\\n"\
            f"\uc0\u21363 \u26102 \u36335 \u20917 \u65306 \{traffic_str\}"\
        )\
        \
        print("\uc0\u55357 \u56481  \u27491 \u22312 \u25552 \u20132  MiMo \u27169 \u22411 \u26500 \u24314 \u26216 \u25253 ...")\
        final_report = call_mimo_llm(raw_prompt)\
        push_page_5(final_report, f"\uc0\u9670  \u26216 \u38388 \u26234 \u33021 \u26089 \u25253  (\{now_bj.strftime('%H:%M')\})")\
        \
    elif mode == "evening":\
        # --- \uc0\u26202 \u38388 \u24314 \u35758 \u36923 \u36753  (17:00) ---\
        is_tomorrow_holiday = check_holiday_api(tomorrow_str) or (len(todos_tomorrow) == 0)\
        has_tomorrow_work = any(any(kw in str(t.get("title", "")) for kw in work_keywords) for t in todos_tomorrow)\
        \
        # \uc0\u24403 \u22825 \u26377 \u20540 \u29677 \u21017 \u26080 \u38656 \u20170 \u26202 \u22238 \u23478 \u36335 \u20917 \
        skip_traffic = duty_today or ( (check_holiday_api(today_str) or len(todos_today)==0) and not any(any(kw in str(t.get("title", "")) for kw in work_keywords) for t in todos_today) )\
        # \uc0\u26126 \u22825 \u22825 \u27668 \u21306 \u22495 \u36873 \u25321 \
        tomorrow_adcode = ADCODE_XINBEI if (is_tomorrow_holiday and not has_tomorrow_work) else ADCODE_TIANNING\
        \
        weather_tomorrow = get_hybrid_weather(tomorrow_adcode)\
        advice_tomorrow = get_clothing_advice(weather_tomorrow["temp_low"], weather_tomorrow["humidity"])\
        \
        traffic_str = "\uc0\u20170 \u26202 \u26657 \u20869 \u20540 \u29677 \u25110 \u20551 \u26399 \u35905 \u20813 \u36335 \u20917 \u12290 " if skip_traffic else get_traffic_info(ADDR_SCHOOL, ADDR_HOME, AMAP_KEY)\
        todo_str = "\uc0\u12289 ".join([t.get("title", "") for t in todos_tomorrow]) if todos_tomorrow else "\u26126 \u26085 \u26242 \u26080 \u29305 \u27530 \u23433 \u25490 "\
        \
        raw_prompt = (\
            f"\uc0\u12304 \u26202 \u25253 \u25968 \u25454 \u12305 \\n"\
            f"\uc0\u39044 \u25253 \u26085 \u26399 \u65306 \u26126 \u26085 (\{tomorrow_str\})\\n"\
            f"\uc0\u26126 \u26085 \u27668 \u35937 \u39044 \u27979 \u65306 \{'\u26032 \u21271 \u20027 \u23478 ' if tomorrow_adcode==ADCODE_XINBEI else '\u22825 \u23425 \u26657 \u21306 '\}\'b7\{weather_tomorrow['weather']\}\u65292 \u27668 \u28201 \{weather_tomorrow['temp_low']\}\'b0~\{weather_tomorrow['temp_high']\}\'b0\u12290 \\n"\
            f"\uc0\u22791 \u34915 \u24314 \u35758 \u65306 \{advice_tomorrow\}\\n"\
            f"\uc0\u26126 \u26085 \u34892 \u31243 \u39044 \u21578 \u65306 \{todo_str\}\\n"\
            f"\uc0\u20170 \u26202 \u36820 \u31243 \u36335 \u20917 \u65306 \{traffic_str\}"\
        )\
        \
        print("\uc0\u55357 \u56481  \u27491 \u22312 \u25552 \u20132  MiMo \u27169 \u22411 \u26500 \u24314 \u26202 \u25253 ...")\
        final_report = call_mimo_llm(raw_prompt)\
        push_page_5(final_report, f"\uc0\u9670  \u26202 \u38388 \u36148 \u24515 \u31569 \u26790  (\{now_bj.strftime('%H:%M')\})")\
\
if __name__ == "__main__":\
    main()}