"""
Voice-Activated Personal Assistant
====================================
Features:
  - Speech recognition (microphone or text fallback)
  - Text-to-speech responses
  - Weather checking (wttr.in API - no key needed)
  - News headlines (NewsAPI or RSS fallback)
  - Reminders with scheduling
  - Wikipedia quick facts
  - Time & Date queries
  - Jokes
  - Calculator
  - System commands (open apps, search web)
"""

import speech_recognition as sr
import pyttsx3
import requests
import datetime
import threading
import schedule
import time
import re
import json
import webbrowser
import random
import math
import wikipedia  # optional – handled with try/except
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
#  TTS ENGINE
# ─────────────────────────────────────────────
engine = pyttsx3.init()
engine.setProperty("rate", 170)
engine.setProperty("volume", 1.0)

def speak(text: str):
    """Convert text to speech and also print it."""
    print(f"\n🤖 Assistant: {text}")
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass  # graceful fallback if audio device unavailable


# ─────────────────────────────────────────────
#  SPEECH RECOGNITION
# ─────────────────────────────────────────────
recognizer = sr.Recognizer()
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True

def listen() -> str:
    """Listen via microphone; fall back to keyboard input on error."""
    print("\n🎤 Listening... (or press Enter to type)")
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)
        text = recognizer.recognize_google(audio)
        print(f"👤 You said: {text}")
        return text.lower()
    except sr.WaitTimeoutError:
        return _text_fallback()
    except sr.UnknownValueError:
        speak("Sorry, I didn't catch that. Could you repeat?")
        return ""
    except sr.RequestError:
        speak("Speech service is unavailable. Switching to text input.")
        return _text_fallback()
    except OSError:
        # No microphone available
        return _text_fallback()

def _text_fallback() -> str:
    try:
        user_input = input("⌨️  Type your command: ").strip()
        return user_input.lower()
    except (EOFError, KeyboardInterrupt):
        return "exit"


# ─────────────────────────────────────────────
#  REMINDERS
# ─────────────────────────────────────────────
reminders: list[dict] = []

def set_reminder(text: str):
    """Parse and set a reminder from natural language."""
    # Try to find time like "in 5 minutes", "at 3pm", "in 1 hour"
    in_match = re.search(r"in (\d+) (minute|minutes|min|hour|hours)", text)
    at_match = re.search(r"at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)

    reminder_text_match = re.search(r"(?:to|that|about|for)\s+(.+?)(?:\s+in\s+|\s+at\s+|$)", text)
    reminder_label = reminder_text_match.group(1).strip() if reminder_text_match else "your reminder"

    if in_match:
        amount = int(in_match.group(1))
        unit = in_match.group(2)
        seconds = amount * 60 if "min" in unit else amount * 3600
        trigger_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        _schedule_reminder(reminder_label, trigger_time, seconds)
        speak(f"Got it! I'll remind you to {reminder_label} in {amount} {'minute' if 'min' in unit else 'hour'}{'s' if amount > 1 else ''}.")
    elif at_match:
        hour = int(at_match.group(1))
        minute = int(at_match.group(2)) if at_match.group(2) else 0
        period = at_match.group(3)
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        now = datetime.datetime.now()
        trigger_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if trigger_time <= now:
            trigger_time += datetime.timedelta(days=1)
        delay = (trigger_time - now).total_seconds()
        _schedule_reminder(reminder_label, trigger_time, delay)
        speak(f"Reminder set for {trigger_time.strftime('%I:%M %p')} to {reminder_label}.")
    else:
        speak("I couldn't understand the time. Try saying 'remind me to call mom in 10 minutes'.")

def _schedule_reminder(label: str, trigger_time: datetime.datetime, delay_seconds: float):
    reminder = {"label": label, "time": trigger_time}
    reminders.append(reminder)

    def _fire():
        speak(f"⏰ Reminder: {label}!")
        reminders.remove(reminder)

    timer = threading.Timer(delay_seconds, _fire)
    timer.daemon = True
    timer.start()

def list_reminders():
    if not reminders:
        speak("You have no active reminders.")
    else:
        speak(f"You have {len(reminders)} reminder{'s' if len(reminders) > 1 else ''}:")
        for r in reminders:
            speak(f"  • {r['label']} at {r['time'].strftime('%I:%M %p')}")


# ─────────────────────────────────────────────
#  WEATHER
# ─────────────────────────────────────────────
def get_weather(query: str):
    """Get weather using wttr.in (no API key required)."""
    # Extract city from query
    city_match = re.search(r"(?:weather|temperature|forecast)\s+(?:in|at|for)?\s+([a-zA-Z\s]+?)(?:\?|$)", query)
    city = city_match.group(1).strip() if city_match else "Delhi"
    city_slug = city.replace(" ", "+")

    try:
        url = f"https://wttr.in/{city_slug}?format=j1"
        resp = requests.get(url, timeout=8)
        data = resp.json()
        current = data["current_condition"][0]
        temp_c = current["temp_C"]
        feels_c = current["FeelsLikeC"]
        desc = current["weatherDesc"][0]["value"]
        humidity = current["humidity"]
        wind = current["windspeedKmph"]

        msg = (f"Weather in {city}: {desc}. "
               f"Temperature is {temp_c}°C, feels like {feels_c}°C. "
               f"Humidity {humidity}%, wind speed {wind} km/h.")
        speak(msg)
    except Exception as e:
        speak(f"Sorry, I couldn't fetch the weather for {city}. Please check your internet connection.")


# ─────────────────────────────────────────────
#  NEWS
# ─────────────────────────────────────────────
def get_news(query: str = ""):
    """Fetch top headlines using Google News RSS (no API key needed)."""
    topic_match = re.search(r"news\s+(?:about|on|for)?\s+([a-zA-Z\s]+?)(?:\?|$)", query)
    topic = topic_match.group(1).strip() if topic_match else ""

    try:
        if topic:
            url = f"https://news.google.com/rss/search?q={topic.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
        else:
            url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"

        resp = requests.get(url, timeout=8)
        soup = BeautifulSoup(resp.content, "xml")
        items = soup.find_all("item")[:5]

        if not items:
            speak("No news found right now.")
            return

        speak(f"Here are the top {'headlines' if not topic else topic + ' news'} headlines:")
        for i, item in enumerate(items, 1):
            title = item.find("title").text
            # Clean up - remove source suffix like " - CNN"
            title = re.sub(r"\s+-\s+\S+$", "", title)
            speak(f"{i}. {title}")
    except Exception:
        speak("Sorry, I couldn't fetch the news right now.")


# ─────────────────────────────────────────────
#  WIKIPEDIA
# ─────────────────────────────────────────────
def search_wikipedia(query: str):
    topic_match = re.search(r"(?:what is|who is|tell me about|search|define)\s+(.+?)(?:\?|$)", query)
    topic = topic_match.group(1).strip() if topic_match else query

    try:
        import wikipedia as wiki
        wiki.set_lang("en")
        summary = wiki.summary(topic, sentences=3, auto_suggest=True)
        speak(summary)
    except Exception:
        # Fallback: DuckDuckGo instant answer
        try:
            url = f"https://api.duckduckgo.com/?q={topic.replace(' ', '+')}&format=json&no_html=1"
            data = requests.get(url, timeout=6).json()
            abstract = data.get("AbstractText", "")
            if abstract:
                speak(abstract[:400])
            else:
                speak(f"I couldn't find information about {topic}. Opening a web search instead.")
                webbrowser.open(f"https://www.google.com/search?q={topic.replace(' ', '+')}")
        except Exception:
            speak(f"I couldn't find information about {topic}.")


# ─────────────────────────────────────────────
#  TIME & DATE
# ─────────────────────────────────────────────
def tell_time():
    now = datetime.datetime.now()
    speak(f"The current time is {now.strftime('%I:%M %p')}.")

def tell_date():
    now = datetime.datetime.now()
    speak(f"Today is {now.strftime('%A, %B %d, %Y')}.")


# ─────────────────────────────────────────────
#  CALCULATOR
# ─────────────────────────────────────────────
def calculate(query: str):
    # Extract math expression
    expr = re.sub(r"[^0-9+\-*/().% ]", "", query)
    expr = expr.strip()
    if not expr:
        speak("I couldn't find a math expression to calculate.")
        return
    try:
        result = eval(expr, {"__builtins__": {}}, {"sqrt": math.sqrt, "pi": math.pi})
        speak(f"The result of {expr} is {round(result, 6)}.")
    except Exception:
        speak("I couldn't calculate that. Please try rephrasing.")


# ─────────────────────────────────────────────
#  JOKES
# ─────────────────────────────────────────────
JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "I told my computer I needed a break. Now it won't stop sending me KitKat ads.",
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "How many programmers does it take to change a light bulb? None — it's a hardware problem.",
    "Why did the robot go on a diet? It had too many bytes.",
    "What do you call a sleeping dinosaur? A dino-snore.",
    "I asked Siri why I'm still single. She opened the front camera.",
]

def tell_joke():
    speak(random.choice(JOKES))


# ─────────────────────────────────────────────
#  WEB SEARCH / OPEN
# ─────────────────────────────────────────────
def open_website(query: str):
    sites = {
        "youtube": "https://youtube.com",
        "google": "https://google.com",
        "github": "https://github.com",
        "gmail": "https://mail.google.com",
        "maps": "https://maps.google.com",
        "wikipedia": "https://wikipedia.org",
        "twitter": "https://twitter.com",
        "reddit": "https://reddit.com",
    }
    for name, url in sites.items():
        if name in query:
            webbrowser.open(url)
            speak(f"Opening {name}.")
            return
    # Generic web search
    search_term = re.sub(r"(open|search|browse|go to|visit|look up)", "", query).strip()
    if search_term:
        webbrowser.open(f"https://www.google.com/search?q={search_term.replace(' ', '+')}")
        speak(f"Searching Google for {search_term}.")


# ─────────────────────────────────────────────
#  INTENT ROUTING
# ─────────────────────────────────────────────
def process_command(command: str) -> bool:
    """Route a command string to the appropriate handler. Returns False to quit."""
    if not command:
        return True

    cmd = command.lower().strip()

    # Exit
    if any(w in cmd for w in ["exit", "quit", "bye", "goodbye", "stop", "shut down"]):
        speak("Goodbye! Have a wonderful day.")
        return False

    # Time & Date
    elif any(w in cmd for w in ["what time", "current time", "tell me the time"]):
        tell_time()

    elif any(w in cmd for w in ["what date", "today's date", "what day", "current date"]):
        tell_date()

    # Weather
    elif any(w in cmd for w in ["weather", "temperature", "forecast", "rain", "humidity"]):
        get_weather(cmd)

    # News
    elif "news" in cmd or "headlines" in cmd:
        get_news(cmd)

    # Reminders
    elif "remind" in cmd or "set a reminder" in cmd or "set reminder" in cmd:
        set_reminder(cmd)

    elif any(w in cmd for w in ["my reminders", "list reminders", "show reminders", "what reminders", "reminders"]) and "remind" not in cmd:
        list_reminders()

    # Wikipedia / facts
    elif any(w in cmd for w in ["what is", "who is", "tell me about", "explain", "define"]):
        search_wikipedia(cmd)

    # Calculator
    elif any(w in cmd for w in ["calculate", "compute", "what is", "how much is"]) and any(c in cmd for c in "0123456789"):
        calculate(cmd)

    # Joke
    elif any(w in cmd for w in ["joke", "funny", "make me laugh", "tell me a joke"]):
        tell_joke()

    # Open / Search
    elif any(w in cmd for w in ["open", "search", "browse", "go to", "visit"]):
        open_website(cmd)

    # Greetings
    elif any(w in cmd for w in ["hello", "hi", "hey", "good morning", "good evening", "good afternoon"]):
        hour = datetime.datetime.now().hour
        greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        speak(f"{greet}! I'm your personal assistant. How can I help you today?")

    # Help
    elif any(w in cmd for w in ["help", "what can you do", "capabilities", "features"]):
        speak(
            "I can help you with: "
            "checking the weather, reading the latest news, "
            "setting reminders, telling the time and date, "
            "answering Wikipedia questions, doing calculations, "
            "telling jokes, and opening websites. "
            "Just ask me anything!"
        )

    else:
        speak(f"I'm not sure how to help with '{command}'. Try asking for weather, news, reminders, or say 'help'.")

    return True


# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  🎙️  VOICE-ACTIVATED PERSONAL ASSISTANT")
    print("=" * 55)
    print("  Commands: weather, news, reminders, time, date,")
    print("            jokes, calculate, open [site], help, exit")
    print("=" * 55)

    speak("Hello! I'm your voice-activated personal assistant. Say 'help' to hear what I can do, or just ask me anything!")

    running = True
    while running:
        command = listen()
        running = process_command(command)

    print("\n✅ Assistant shut down cleanly.")


if __name__ == "__main__":
    main()