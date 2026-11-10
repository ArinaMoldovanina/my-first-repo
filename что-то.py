"""
AIhelper - Локальный AI-помощник с графическим интерфейсом.
Требует установленные библиотеки: pip install pytz tzlocal edge_tts pygame
Убедитесь, что Ollama запущена и модель qwen2.5:3b установлена.
"""

import json
import os
import re
import asyncio
import tempfile
import threading
import queue
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote
from datetime import datetime
import pytz
from tzlocal import get_localzone
import edge_tts
import pygame
import tkinter as tk
from tkinter import filedialog

# ==========================================
# КОНФИГУРАЦИЯ
# ==========================================
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:3b"
MEMORY_FILE = str(Path(__file__).resolve().parent / "memory.json")
MAX_HISTORY = 20
MAX_FILE_SIZE = 100_000
TTS_VOICE = "ru-RU-SvetlanaNeural"
TTS_RATE = "+0%"
TTS_VOLUME = "+0%"
WEATHER_URL = "https://wttr.in/{city}?format=j1&lang=ru"

LOCAL_TIMEZONE = str(get_localzone())

SYSTEM_PROMPT = f"""
Ты полезный универсальный помощник по имени AIhelper.
Отвечай на русском языке, если пользователь не попросил другой язык.
Объясняй понятно и по делу.
Если пишешь код, всегда используй блоки кода.
Не выдумывай факты. Если не уверен, честно скажи об этом.
У тебя есть доступ к инструментам для работы с часовыми поясами.
Часовой пояс пользователя: {LOCAL_TIMEZONE}.
""".strip()

# ==========================================
# ФУНКЦИИ РАБОТЫ С СОСТОЯНИЕМ
# ==========================================
def load_state():
    if not os.path.exists(MEMORY_FILE):
        return {"history": [], "document": "", "custom_prompt": ""}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)
        return {
            "history": state.get("history", []),
            "document": state.get("document", ""),
            "custom_prompt": state.get("custom_prompt", "")
        }
    except Exception:
        return {"history": [], "document": "", "custom_prompt": ""}

def save_state(state):
    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)

# ==========================================
# ИНСТРУМЕНТЫ ДЛЯ ЧАСОВЫХ ПОЯСОВ
# ==========================================
def get_current_time(timezone_str=None):
    if timezone_str is None:
        timezone_str = LOCAL_TIMEZONE
    try:
        tz = pytz.timezone(timezone_str)
        current_time = datetime.now(tz)
        return {
            "timezone": timezone_str,
            "datetime": current_time.strftime('%Y-%m-%d %H:%M:%S'),
            "date": current_time.strftime('%d %B %Y'),
            "time": current_time.strftime('%H:%M:%S'),
            "weekday": current_time.strftime('%A')
        }
    except Exception as e:
        return {"error": f"Не удалось получить время для {timezone_str}: {str(e)}"}

def convert_timezone(source_time_str, source_tz_str=None, target_tz_str=None):
    if source_tz_str is None:
        source_tz_str = LOCAL_TIMEZONE
    if target_tz_str is None:
        target_tz_str = LOCAL_TIMEZONE
    try:
        source_tz = pytz.timezone(source_tz_str)
        target_tz = pytz.timezone(target_tz_str)
        if len(source_time_str) <= 5:
            today = datetime.now().strftime('%Y-%m-%d')
            source_time_str = f"{today} {source_time_str}:00"
        source_dt = datetime.strptime(source_time_str, '%Y-%m-%d %H:%M:%S')
        source_dt = source_tz.localize(source_dt)
        target_dt = source_dt.astimezone(target_tz)
        return {
            "source": {"timezone": source_tz_str, "datetime": source_dt.strftime('%Y-%m-%d %H:%M:%S')},
            "target": {
                "timezone": target_tz_str,
                "datetime": target_dt.strftime('%Y-%m-%d %H:%M:%S'),
                "date": target_dt.strftime('%d %B %Y'),
                "time": target_dt.strftime('%H:%M:%S')
            }
        }
    except Exception as e:
        return {"error": f"Ошибка конвертации: {str(e)}"}

def list_timezones():
    return {"timezones": pytz.all_timezones[:50]}

TOOLS = {
    "get_current_time": get_current_time,
    "convert_timezone": convert_timezone,
    "list_timezones": list_timezones
}

    
# ==========================================
# ФУНКЦИИ ДЛЯ ПОГОДЫ
# ==========================================
def get_weather(city):
    city_encoded = quote(city)
    url = WEATHER_URL.format(city=city_encoded)
    request = Request(url, headers={"User-Agent": "curl/7.68.0"})
    
    try:
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        
        current = data["current_condition"][0]
        if "lang_ru" in current and current["lang_ru"]:
            description = current["lang_ru"][0].get("value", "")
        else:
            description = current.get("weatherDesc", [{}])[0].get("value", "нет данных")
        
        forecast = []
        for day in data.get("weather", [])[:3]:
            hourly = day.get("hourly", [])
            noon = hourly[4] if len(hourly) > 4 else hourly[0] if hourly else {}
            if "lang_ru" in noon and noon["lang_ru"]:
                day_desc = noon["lang_ru"][0].get("value", "")
            else:
                day_desc = noon.get("weatherDesc", [{}])[0].get("value", "нет данных")
            forecast.append({
                "date": day["date"],
                "max_temp": day["maxtempC"],
                "min_temp": day["mintempC"],
                "description": day_desc
            })
        
        return {
            "city": city, "temp_c": current["temp_C"], "feels_like": current["FeelsLikeC"],
            "description": description, "humidity": current["humidity"],
            "wind_speed": current["windspeedKmph"], "wind_dir": current["winddir16Point"],
            "pressure": current["pressure"], "visibility": current["visibility"],
            "precip_mm": current["precipMM"], "uv_index": current["uvIndex"], "forecast": forecast
        }
    except HTTPError as e:
        return {"error": f"Город '{city}' не найден." if e.code == 404 else f"Ошибка HTTP: {e.code}"}
    except URLError as e:
        return {"error": f"Нет подключения к интернету: {e.reason}"}
    except Exception as e:
        return {"error": f"Ошибка: {str(e)}"}

def handle_weather_query(user_text):
    text_lower = user_text.lower().strip()
    weather_keywords = ["погода", "погоду", "погодой", "прогноз", "температура", "тепло", "холодно", "жарко", "дождь", "снег", "ветер"]
    if not any(kw in text_lower for kw in weather_keywords):
        return None
    
    weather_patterns = [
        r"погода\s+(?:в|во|на)\s+(.+?)(?:\?|$)",
        r"какая\s+(?:сейчас\s+)?погода\s+(?:в|во|на)\s+(.+?)(?:\?|$)",
        r"(?:прогноз|погод(?:а|у))\s+(?:на\s+)?(?:\d+\s+дня?|недел(?:ю|и)|завтра)?\s*(?:в|во|на)\s+(.+?)(?:\?|$)",
    ]
    
    city = None
    for pattern in weather_patterns:
        match = re.search(pattern, text_lower)
        if match:
            city = match.group(1).strip().rstrip("?.!,")
            break
    
    if not city:
        known_cities = ["москва", "санкт-петербург", "питер", "спб", "новосибирск", "екатеринбург", "казань", "нижний новгород", "самара", "омск", "челябинск", "уфа", "красноярск", "пермь", "воронеж", "волгоград", "краснодар", "саратов", "тюмень", "тольятти", "ижевск", "барнаул", "ульяновск", "иркутск", "владивосток", "ярославль", "хабаровск", "махачкала", "томск", "оренбург", "кемерово", "новокузнецк", "рязань", "астрахань", "пенза", "набережные челны", "липецк", "тула", "киров", "чебоксары", "калининград", "брянск", "курск", "магнитогорск", "иваново", "тверь", "ставрополь", "белгород", "сочи", "симферополь", "севастополь", "токио", "нью-йорк", "лондон", "париж", "берлин", "рим", "мадрид", "пекин", "шанхай", "дубай", "сеул", "бангкок", "сингапур", "сидней", "торонто", "лос-анджелес", "чикаго", "майами", "мехико", "сан-паулу", "буэнос-айрес", "каир", "йоханнесбург", "стамбул", "анкара"]
        for c in known_cities:
            if c in text_lower:
                city = c
                break
    
    if not city:
        return "Уточни, пожалуйста, для какого города нужна погода?"
    
    weather = get_weather(city)
    if "error" in weather:
        return f"Не удалось получить погоду: {weather['error']}"
    
    forecast_text = ""
    if weather["forecast"]:
        forecast_lines = [f"  • {day['date']}: {day['description']}, от {day['min_temp']}° до {day['max_temp']}°" for day in weather["forecast"]]
        forecast_text = "\n\nПрогноз на 3 дня:\n" + "\n".join(forecast_lines)
    
    return (f"Погода в городе {weather['city'].title()}:\n"
            f"{weather['description']}, {weather['temp_c']}°C (ощущается как {weather['feels_like']}°C)\n"
            f"Влажность: {weather['humidity']}%, Ветер: {weather['wind_speed']} м/с {weather['wind_dir']}\n"
            f"Давление: {weather['pressure']} гПа, Видимость: {weather['visibility']} км\n"
            f"Осадки: {weather['precip_mm']} мм, УФ-индекс: {weather['uv_index']}{forecast_text}")

# ==========================================
# РАБОТА С НЕЙРОСЕТЬЮ
# ==========================================
def build_messages(state):
    global SYSTEM_PROMPT
    current_prompt = state.get("custom_prompt", "").strip()
    if not current_prompt:
        current_prompt = SYSTEM_PROMPT
        
    local_tz = pytz.timezone(LOCAL_TIMEZONE)
    current_time = datetime.now(local_tz)
    system_text = current_prompt + f"\n\nТекущая дата и время у пользователя: {current_time.strftime('%d %B %Y, %H:%M:%S')} ({LOCAL_TIMEZONE})"
    
    if state.get("document"):
        system_text += f"\n\nПользователь загрузил документ:\n--- НАЧАЛО ---\n{state['document']}\n--- КОНЕЦ ---"
    
    messages = [{"role": "system", "content": system_text}]
    messages.extend(state["history"][-MAX_HISTORY:])
    return messages

def ask_neural_network_with_tools(state, user_text):
    messages = build_messages(state)
    messages.append({"role": "user", "content": user_text})
    
    tools_schema = [
        {"type": "function", "function": {"name": "get_current_time", "description": "Получить текущее время.", "parameters": {"type": "object", "properties": {"timezone": {"type": "string"}}, "required": []}}},
        {"type": "function", "function": {"name": "convert_timezone", "description": "Конвертировать время.", "parameters": {"type": "object", "properties": {"source_time": {"type": "string"}, "source_timezone": {"type": "string"}, "target_timezone": {"type": "string"}}, "required": ["source_time"]}}}
    ]
    
    request_data = {"model": MODEL, "messages": messages, "tools": tools_schema, "stream": False, "options": {"temperature": 0.7}}
    request = Request(OLLAMA_URL, data=json.dumps(request_data).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    
    try:
        with urlopen(request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
        
        message = result["message"]
        if "tool_calls" in message and message["tool_calls"]:
            tool_results = []
            for tool_call in message["tool_calls"]:
                func_name = tool_call["function"]["name"]
                arguments = json.loads(tool_call["function"]["arguments"])
                if func_name in TOOLS:
                    tool_results.append({"tool_call_id": tool_call.get("id", ""), "result": TOOLS[func_name](**arguments)})
            
            messages.append(message)
            for tr in tool_results:
                messages.append({"role": "tool", "content": json.dumps(tr["result"], ensure_ascii=False)})
            
            request_data["messages"] = messages
            request_data.pop("tools", None)
            request = Request(OLLAMA_URL, data=json.dumps(request_data).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            
            with urlopen(request, timeout=300) as response:
                final_result = json.loads(response.read().decode("utf-8"))
            answer = final_result["message"]["content"]
        else:
            answer = message["content"]
        
        state["history"].extend([{"role": "user", "content": user_text}, {"role": "assistant", "content": answer}])
        state["history"] = state["history"][-MAX_HISTORY:]
        save_state(state)
        return answer
    except HTTPError as error:
        return f"Ошибка Ollama: HTTP {error.code}"
    except URLError:
        return "Не удалось подключиться к Ollama. Проверьте, запущена ли она и установлена ли модель."
    except Exception as error:
        return f"Произошла ошибка: {error}"

# ==========================================
# РАБОТА С ФАЙЛАМИ
# ==========================================
def load_document(state, file_path):
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return "Файл не найден."
    if path.stat().st_size > MAX_FILE_SIZE:
        return "Файл слишком большой (макс. 100 КБ)."
    if path.suffix.lower() not in {".txt", ".md", ".py", ".json", ".csv", ".html", ".css", ".js"}:
        return "Неподдерживаемый формат файла."
    try:
        state["document"] = path.read_text(encoding="utf-8")
        save_state(state)
        return f"Файл успешно загружен: {path.name}"
    except Exception as error:
        return f"Ошибка чтения файла: {error}"

# ==========================================
# ОЗВУЧИВАНИЕ (EDGE TTS) + ПОТОКИ
# ==========================================
def init_audio_player():
    try:
        pygame.mixer.init()
    except Exception:
        pass

def clean_text_for_speech(text):
    text = re.sub(r'[\U0001F300-\U0001F9FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF]', '', text)
    text = re.sub(r'`[\s\S]*?`', ' код пропущен. ', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\n{2,}', '. ', text)
    return re.sub(r'\s+', ' ', text).strip()

def split_into_chunks(text, max_length=4000):
    if len(text) <= max_length:
        return [text]
    chunks, current = [], ""
    for sentence in re.split(r'(?<=[.!?…])\s+', text):
        if len(current) + len(sentence) + 1 <= max_length:
            current += (' ' if current else '') + sentence
        else:
            if current: chunks.append(current)
            current = sentence if len(sentence) <= max_length else sentence[:max_length]
    if current: chunks.append(current)
    return chunks

async def generate_speech(text, output_file):
    await edge_tts.Communicate(text=text, voice=TTS_VOICE, rate=TTS_RATE, volume=TTS_VOLUME).save(output_file)

class AudioManager:
    def __init__(self, status_callback):
        self.is_playing = False
        self.is_paused = False
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.thread = None
        self.status_callback = status_callback

    def speak(self, text, muted=False):
        if muted or not text:
            return
        self.stop()
        clean_text = clean_text_for_speech(text)
        if not clean_text:
            return
            
        chunks = split_into_chunks(clean_text)
        self.is_playing = True
        self.is_paused = False
        self.stop_event.clear()
        self.pause_event.set()
        self.status_callback(" Говорю...")
        
        self.thread = threading.Thread(target=self._playback_loop, args=(chunks,))
        self.thread.start()

    def _playback_loop(self, chunks):
        for chunk in chunks:
            if self.stop_event.is_set():
                break
            self.pause_event.wait()
            if self.stop_event.is_set():
                break

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                asyncio.run(generate_speech(chunk, temp_path))
                pygame.mixer.music.load(temp_path)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy() and not self.stop_event.is_set():
                    if not self.pause_event.is_set():
                        pygame.mixer.music.pause()
                        self.status_callback("⏸ На паузе")
                        self.pause_event.wait()
                        if self.stop_event.is_set():
                            break
                        pygame.mixer.music.unpause()
                        self.status_callback("🔊 Говорю...")
                    pygame.time.Clock().tick(10)
            except Exception as error:
                print(f"[Ошибка озвучки: {error}]")
            finally:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception:
                    pass
        
        self.is_playing = False
        self.is_paused = False
        pygame.mixer.music.stop()
        self.status_callback("✅ Готово")

    def toggle_pause(self):
        if self.is_playing:
            self.is_paused = not self.is_paused
            if self.is_paused:
                pygame.mixer.music.pause()
                self.pause_event.clear()
                self.status_callback("⏸ На паузе")
            else:
                pygame.mixer.music.unpause()
                self.pause_event.set()
                self.status_callback("🔊 Говорю...")

    def stop(self):
        if self.is_playing:
            self.stop_event.set()
            self.pause_event.set()
            pygame.mixer.music.stop()
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1.0)
            self.is_playing = False
            self.is_paused = False
            self.status_callback("⏹ Остановлено")

# ==========================================
# СТАБИЛЬНЫЙ И СОВРЕМЕННЫЙ GUI
# ==========================================
class AIhelperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AIhelper")
        self.root.geometry("850x700")
        self.root.minsize(600, 400)
        
        # Современная темная цветовая схема
        self.bg_color = "#000000"          # Темный фон (Slate 900)
        self.header_bg = "#28497A"         # Фон шапки (Slate 800)
        self.bubble_user = "#3B82F6"       # Синий пузырь пользователя
        self.bubble_ai = "#5D5A96"         # Серый пузырь AI
        self.text_primary = "#F8FAFC"      # Белый текст
        self.text_secondary = "#0C2E7E"    # Серый текст
        self.input_bg = "#28497A"          # Фон поля ввода
        self.border_color = "#334155"      # Цвет границ
        
        self.root.configure(bg=self.bg_color)
        
        self.state = load_state()
        self.muted = False
        self.msg_queue = queue.Queue()
        
        self._init_ui()
        self.audio_manager = AudioManager(self.update_status)
        
        self.root.after(100, self.check_queue)
        init_audio_player()
        self.update_status("✅ AIhelper готов к работе")

    def _init_ui(self):
        # === ШАПКА ===
        header_frame = tk.Frame(self.root, bg=self.header_bg, height=60)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="AIhelper", font=("Segoe UI", 20, "bold"), 
                 bg=self.header_bg, fg=self.text_primary).place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        self.clear_btn = tk.Button(header_frame, text="🗑 Очистить", font=("Segoe UI", 10), 
                                   bg=self.bubble_ai, fg=self.text_primary, relief=tk.FLAT, 
                                   cursor="hand2", padx=10, pady=5, command=self.clear_chat)
        self.clear_btn.place(relx=0.95, rely=0.5, anchor=tk.CENTER)
        
        # === ОБЛАСТЬ ЧАТА ===
        chat_container = tk.Frame(self.root, bg=self.bg_color)
        chat_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.chat_canvas = tk.Canvas(chat_container, bg=self.bg_color, highlightthickness=0)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.scrollbar = tk.Scrollbar(chat_container, orient=tk.VERTICAL, command=self.chat_canvas.yview,
                                      bg=self.bg_color, troughcolor=self.bg_color)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.messages_frame = tk.Frame(self.chat_canvas, bg=self.bg_color)
        self.chat_window = self.chat_canvas.create_window(0, 0, window=self.messages_frame, anchor=tk.NW, width=800)
        
        self.messages_frame.bind("<Configure>", self._on_frame_configure)
        self.chat_canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Приветствие
        self._add_message("Привет! Я AIhelper. Чем могу помочь?", is_user=False)

        # === ОБЛАСТЬ ВВОДА ===
        input_container = tk.Frame(self.root, bg=self.bg_color)
        input_container.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        input_frame = tk.Frame(input_container, bg=self.input_bg, relief=tk.FLAT)
        input_frame.pack(fill=tk.X)
        
        # === АККУРАТНАЯ ТОНКАЯ СКРЕПКА ===
        attach_btn = tk.Label(input_frame, text="+", font=("Segoe UI", 35), 
                              bg=self.input_bg, fg="#FFFFFF", cursor="hand2", 
                              padx=10, pady=10)
        attach_btn.pack(side=tk.LEFT, padx=(15, 10), pady=5)
        attach_btn.bind("<Button-1>", lambda e: self.load_file_dialog())
        attach_btn.bind("<Enter>", lambda e: attach_btn.configure(fg="#93C5FD"))
        attach_btn.bind("<Leave>", lambda e: attach_btn.configure(fg="#60A5FA"))
        
        self.entry = tk.Text(input_frame, font=("Segoe UI", 11), bg=self.input_bg, fg=self.text_primary,
                             insertbackground=self.text_primary, relief=tk.FLAT, wrap=tk.WORD, 
                             height=3, padx=10, pady=10)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=8)
        self.entry.bind("<Return>", self._on_enter_pressed)
        
        # Кнопка отправки
        send_btn = tk.Label(input_frame, text="➤", font=("Segoe UI", 16, "bold"), bg=self.bubble_user, 
                            fg="#FFFFFF", cursor="hand2", padx=12, pady=8)
        send_btn.pack(side=tk.RIGHT, padx=(5, 10), pady=8)
        send_btn.bind("<Button-1>", lambda e: self.send_message())
        
        # Статус бар
        self.status_label = tk.Label(self.root, text="Инициализация...", font=("Segoe UI", 9), 
                                     bg=self.bg_color, fg=self.text_secondary)
        self.status_label.pack(pady=(0, 5))

    def _add_message(self, text, is_user=False):
        """Добавление сообщения с помощью стабильных Label виджетов"""
        msg_container = tk.Frame(self.messages_frame, bg=self.bg_color)
        msg_container.pack(fill=tk.X, pady=6, padx=10, anchor=tk.E if is_user else tk.W)
        
        bubble_color = self.bubble_user if is_user else self.bubble_ai
        text_color = self.text_primary
        
        # wraplength=600 обеспечивает перенос длинных строк
        msg_label = tk.Label(msg_container, text=text, bg=bubble_color, fg=text_color,
                             font=("Segoe UI", 11), wraplength=600, justify=tk.LEFT,
                             padx=15, pady=10)
        msg_label.pack(side=tk.RIGHT if is_user else tk.LEFT)
        
        self._scroll_to_bottom()

    def _on_frame_configure(self, event):
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.chat_canvas.itemconfig(self.chat_window, width=event.width)

    def _scroll_to_bottom(self):
        self.chat_canvas.yview_moveto(1.0)

    def update_status(self, text):
        self.status_label.config(text=text)

    def check_queue(self):
        try:
            while True:
                task = self.msg_queue.get_nowait()
                if task["type"] == "append_chat":
                    self._add_message(task["text"], is_user=task["is_user"])
                elif task["type"] == "speak":
                    self.audio_manager.speak(task["text"], muted=self.muted)
                elif task["type"] == "status":
                    self.update_status(task["text"])
        except queue.Empty:
            pass
        self.root.after(100, self.check_queue)

    def send_message(self):
        user_text = self.entry.get("1.0", tk.END).strip()
        if not user_text:
            return
            
        self.entry.delete("1.0", tk.END)
        self.msg_queue.put({"type": "append_chat", "text": user_text, "is_user": True})
        self.update_status("⏳ Думаю...")
        
        if self.audio_manager.is_playing or self.audio_manager.is_paused:
            self.audio_manager.stop()
            
        threading.Thread(target=self.process_request, args=(user_text,), daemon=True).start()

    def _on_enter_pressed(self, event):
        if event.state & 0x1:  # Shift+Enter для новой строки
            return None
        self.send_message()
        return "break"

    def process_request(self, user_text):
        if user_text == "/clear":
            self.state["history"] = []
            save_state(self.state)
            self.msg_queue.put({"type": "append_chat", "text": "Память диалога очищена.", "is_user": False})
            self.update_status("✅ Готово")
            return
            
        if user_text == "/mute":
            self.toggle_mute()
            return

        weather_answer = handle_weather_query(user_text)
        if weather_answer:
            self.msg_queue.put({"type": "append_chat", "text": weather_answer, "is_user": False})
            self.msg_queue.put({"type": "speak", "text": weather_answer})
            
            self.state["history"].extend([{"role": "user", "content": user_text}, {"role": "assistant", "content": weather_answer}])
            self.state["history"] = self.state["history"][-MAX_HISTORY:]
            save_state(self.state)
            self.update_status("✅ Готово")
            return

        answer = ask_neural_network_with_tools(self.state, user_text)
        self.msg_queue.put({"type": "append_chat", "text": answer, "is_user": False})
        self.msg_queue.put({"type": "speak", "text": answer})
        self.update_status("✅ Готово")

    def toggle_pause(self):
        self.audio_manager.toggle_pause()

    def toggle_mute(self):
        self.muted = not self.muted
        self.update_status(f"Озвучка {'выключена' if self.muted else 'включена'}")

    def load_file_dialog(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt *.md *.py *.json *.csv *.html *.css *.js")])
        if file_path:
            result = load_document(self.state, file_path)
            self.msg_queue.put({"type": "append_chat", "text": result, "is_user": False})

    def clear_chat(self):
        for widget in self.messages_frame.winfo_children():
            widget.destroy()
        self._add_message("Привет! Я AIhelper. Чем могу помочь?", is_user=False)
        self.state["history"] = []
        save_state(self.state)
        self.update_status("✅ История очищена")

def main():
    root = tk.Tk()
    app = AIhelperApp(root)
    
    def on_closing():
        app.audio_manager.stop()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()