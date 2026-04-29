"""
Sentiment Analysis Web App — Flask + TextBlob
=============================================
Routes:
  GET  /          → main UI page
  POST /analyze   → returns JSON sentiment result
  GET  /history   → returns last 10 analyses (in-memory)
"""

from flask import Flask, render_template, request, jsonify
from textblob import TextBlob
from datetime import datetime

app = Flask(__name__)

# In-memory history (last 20 entries)
history = []


def classify_sentiment(polarity: float) -> dict:
    """Map polarity score to label, emoji, and CSS class."""
    if polarity > 0.1:
        return {"label": "Positive", "emoji": "😊", "css": "positive"}
    elif polarity < -0.1:
        return {"label": "Negative", "emoji": "😞", "css": "negative"}
    else:
        return {"label": "Neutral",  "emoji": "😐", "css": "neutral"}


def classify_subjectivity(score: float) -> str:
    if score < 0.33:
        return "Objective"
    elif score < 0.66:
        return "Mixed"
    else:
        return "Subjective"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "Please enter some text to analyze."}), 400

    if len(text) > 5000:
        return jsonify({"error": "Text is too long. Please keep it under 5000 characters."}), 400

    blob = TextBlob(text)
    polarity    = round(blob.sentiment.polarity, 4)
    subjectivity = round(blob.sentiment.subjectivity, 4)

    sentiment = classify_sentiment(polarity)
    subj_label = classify_subjectivity(subjectivity)

    # Word & sentence count (simple split avoids NLTK punkt dependency)
    words     = len(text.split())
    sentences = max(1, text.count('.') + text.count('!') + text.count('?'))

    result = {
        "text":         text[:120] + ("..." if len(text) > 120 else ""),
        "polarity":     polarity,
        "subjectivity": subjectivity,
        "label":        sentiment["label"],
        "emoji":        sentiment["emoji"],
        "css":          sentiment["css"],
        "subj_label":   subj_label,
        "words":        words,
        "sentences":    sentences,
        "timestamp":    datetime.now().strftime("%H:%M:%S"),
    }

    # Save to history (keep last 20)
    history.insert(0, result)
    if len(history) > 20:
        history.pop()

    return jsonify(result)


@app.route("/history")
def get_history():
    return jsonify(history[:10])


if __name__ == "__main__":
    print("=" * 50)
    print("  🧠 Sentiment Analysis App")
    print("  Visit: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True)