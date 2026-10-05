from flask import Flask, render_template, request
import csv
import re
from collections import Counter
from datetime import datetime

app = Flask(__name__)

total_checked = 0
spam_detected = 0
genuine_detected = 0
history = []

# Suspicious keywords
suspicious_keywords = [
    "free",
    "prize",
    "winner",
    "congratulations",
    "urgent",
    "click",
    "offer",
    "cash",
    "reward",
    "claim"
]

messages = []
labels = []

# Load dataset
with open("dataset/spam.csv", "r", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    for row in reader:
        messages.append(row["message"].lower())
        labels.append(row["label"])

# Create word counters
spam_words = Counter()
ham_words = Counter()

for message, label in zip(messages, labels):
    words = message.split()

    if label == "spam":
        spam_words.update(words)
    else:
        ham_words.update(words)


# Home page
@app.route("/")
def home():

    spam_rate = 0

    if total_checked > 0:
        spam_rate = round((spam_detected / total_checked) * 100, 1)

    return render_template(
        "index.html",
        total_checked=total_checked,
        spam_detected=spam_detected,
        genuine_detected=genuine_detected,
        spam_rate=spam_rate,
        history=history
    )


# Check message
@app.route("/check", methods=["POST"])
def check_message():

    global total_checked
    global spam_detected
    global genuine_detected

    message = request.form["message"].lower()

    total_checked += 1

    words = re.findall(r'\b\w+\b', message)

    # Find suspicious keywords
    found_keywords = []

    for word in suspicious_keywords:
        if word in words:
            found_keywords.append(word)

    # Find suspicious links
    found_links = re.findall(
        r"https?://\S+|www\.\S+",
        message
    )

    # Calculate spam and genuine scores
    spam_score = sum(spam_words[word] for word in words)
    ham_score = sum(ham_words[word] for word in words)

    # Current date and time
    checked_time = datetime.now().strftime("%d %b %Y, %I:%M %p")

    # Detection summary
    summary = f"{len(found_keywords)} suspicious keyword(s) and {len(found_links)} link(s) detected."

    # Spam detection
    if spam_score > ham_score:

        spam_detected += 1
        if found_keywords and found_links:
            risk_level = "🔴 HIGH RISK"
        elif found_keywords or found_links:
            risk_level = "🟠 MEDIUM RISK"
        else:
            risk_level = "🟡 LOW RISK"

        result = "🚨 SPAM MESSAGE"

        if found_keywords and found_links:
            reason = "Suspicious keywords and link detected."

        elif found_keywords:
            reason = "Suspicious keywords detected."

        elif found_links:
            reason = "Suspicious link detected."

        else:
            reason = "Message content matches spam patterns."

        suggestion = (
            "Avoid clicking unknown links or sharing personal information."
        )

        alternative = (
            "Please verify the sender and offer through an official "
            "source before taking any action."
        )

    # Genuine detection
    else:

        genuine_detected += 1

        result = "✅ NOT SPAM / GENUINE MESSAGE"
        risk_level = "🟢 LOW RISK"

        if found_keywords or found_links:
            reason = "No strong spam pattern detected."

        else:
            reason = "No suspicious content detected."

        suggestion = (
            "No major safety concern detected. Still verify unknown senders."
        )

        alternative = (
            "This message can be shared normally if you trust the sender."
        )

    # Save message in history
    history.append({
        "message": message,
        "result": result,
        "reason": reason,
        "suggestion": suggestion,
        "alternative": alternative,
        "keywords": found_keywords,
        "links": found_links,
        "time": checked_time,
        "risk": risk_level,
        "summary": summary
    })

    # Calculate spam rate
    spam_rate = round(
        (spam_detected / total_checked) * 100,
        1
    )

    return render_template(
        "index.html",
        result=result,
        total_checked=total_checked,
        spam_detected=spam_detected,
        genuine_detected=genuine_detected,
        spam_rate=spam_rate,
        history=history
    )

# Spam details page
@app.route("/spam-details")
def spam_details():
    if history:
        return render_template(
            "spam_details.html",
            data=history[-1]
        )

    return render_template("index.html")

# Genuine details page
@app.route("/genuine-details")
def genuine_details():
    if history:
        return render_template(
            "genuine_details.html",
            data=history[-1]
        )

    return render_template("index.html")
# Start Flask
if __name__ == "__main__":
    app.run(debug=True)