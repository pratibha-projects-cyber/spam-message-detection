from flask import Flask, render_template, request, redirect, url_for, session
import csv
import re
from collections import Counter
from datetime import datetime
import sqlite3

app = Flask(__name__)

app.secret_key = "fake-message-detection-secret"

total_checked = 0
spam_detected = 0
genuine_detected = 0
history = []


# Create permanent database
def init_db():
    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    # History table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            result TEXT,
            reason TEXT,
            suggestion TEXT,
            alternative TEXT,
            keywords TEXT,
            links TEXT,
            time TEXT,
            risk TEXT,
            summary TEXT
        )
    """)

    # Add user_id to old history table
    try:
        cursor.execute(
            "ALTER TABLE history ADD COLUMN user_id INTEGER"
        )
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


init_db()


# Load previous history
def load_history():
    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT message, result, reason, suggestion, alternative,
               keywords, links, time, risk, summary
        FROM history
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    loaded_history = []

    for row in rows:
        loaded_history.append({
            "message": row[0],
            "result": row[1],
            "reason": row[2],
            "suggestion": row[3],
            "alternative": row[4],
            "keywords": row[5].split(", ") if row[5] else [],
            "links": row[6].split(", ") if row[6] else [],
            "time": row[7],
            "risk": row[8],
            "summary": row[9]
        })

    return loaded_history


history = load_history()


# Susspicious keywords
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


# Load dataset
messages = []
labels = []

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


# Login page
@app.route("/login")
def login():
    return render_template("login.html")


# Login processing
@app.route("/login", methods=["POST"])
def login_post():

    username = request.form["username"]
    password = request.form["password"]

    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, username FROM users WHERE username=? AND password=?",
        (username, password)
    )

    user = cursor.fetchone()
    conn.close()

    if user:
        session["user_id"] = user[0]
        session["username"] = user[1]

        return redirect(url_for("home"))

    return "Invalid username or password"


# Signup page
@app.route("/signup")
def signup():
    return render_template("signup.html")


# Signup processing
@app.route("/signup", methods=["POST"])
def signup_post():

    username = request.form["username"]
    password = request.form["password"]

    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password)
        )

        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()
        return "Username already exists. Please choose another username."

    conn.close()

    return redirect(url_for("login"))


# Logout
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))



# Home page
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT message, result, reason, suggestion, alternative,
               keywords, links, time, risk, summary
        FROM history
        WHERE user_id = ?
        ORDER BY id ASC
    """, (session["user_id"],))

    rows = cursor.fetchall()
    conn.close()

    user_history = []

    for row in rows:
        user_history.append({
            "message": row[0],
            "result": row[1],
            "reason": row[2],
            "suggestion": row[3],
            "alternative": row[4],
            "keywords": [
                w.strip() for w in (row[5] or "").split(",")
                if w.strip()
            ],
            "links": [
                link.strip() for link in (row[6] or "").split(",")
                if link.strip()
            ],
            "time": row[7],
            "risk": row[8],
            "summary": row[9]
        })


    # Monthly Overview
    from datetime import datetime

    current_month = datetime.now().month
    current_year = datetime.now().year

    monthly_history = []

    for item in user_history:
        try:
            checked_date = datetime.strptime(
                item["time"], "%d %b %Y, %I:%M %p"
            )

            if (checked_date.month == current_month
                    and checked_date.year == current_year):
                monthly_history.append(item)

        except (ValueError, TypeError):
            continue

    monthly_total = len(monthly_history)

    monthly_spam = sum(
        1 for item in monthly_history
        if "SPAM MESSAGE" in item["result"]
        and "NOT SPAM" not in item["result"]
    )

    monthly_genuine = sum(
        1 for item in monthly_history
        if "GENUINE" in item["result"]
    )

    # Safe Protection Suggestion
    if monthly_spam > 0:
        safe_suggestion = (
            "Stay alert! Check the sender carefully, "
            "avoid unknown links, and never share OTPs "
            "or personal information with unverified sources."
        )
    else:
        safe_suggestion = (
            "Keep protecting yourself: verify unknown senders "
            "and check links before opening them."
        )
    # Dashboard statistics
    total_checked = len(user_history)

    spam_detected = sum(
        1 for item in user_history
        if "SPAM MESSAGE" in item["result"]
        and "NOT SPAM" not in item["result"]
    )

    genuine_detected = sum(
        1 for item in user_history
        if "GENUINE" in item["result"]
    )

    spam_rate = round(
        spam_detected * 100 / total_checked, 1
    ) if total_checked else 0

    # Bar chart counts
    prize_count = 0
    money_count = 0
    offer_count = 0
    verification_count = 0
    link_count = 0
    urgent_count = 0

    for item in user_history:
        keywords = [w.lower() for w in item["keywords"]]

        if any(w in keywords for w in ["prize", "reward", "winner"]):
            prize_count += 1

        if any(w in keywords for w in ["cash", "money"]):
            money_count += 1

        if any(w in keywords for w in ["offer", "free"]):
            offer_count += 1

        if any(w in keywords for w in ["account", "verify", "verification"]):
            verification_count += 1

        if item["links"]:
            link_count += 1

        if "urgent" in keywords:
            urgent_count += 1

    return render_template(
        "index.html",
        total_checked=total_checked,
        spam_detected=spam_detected,
        genuine_detected=genuine_detected,
        spam_rate=spam_rate,
        history=user_history,
        prize_count=prize_count,
        money_count=money_count,
        offer_count=offer_count,
        verification_count=verification_count,
        link_count=link_count,
        urgent_count=urgent_count,
        
        monthly_total=monthly_total,
        monthly_spam=monthly_spam,
        monthly_genuine=monthly_genuine,
        safe_suggestion=safe_suggestion

       
    )

# Check message
@app.route("/check", methods=["POST"])
def check_message():

    global total_checked
    global spam_detected
    global genuine_detected

    if "user_id" not in session:
        return redirect(url_for("login"))

    message = request.form["message"].lower()

    total_checked += 1

    words = re.findall(r"\b\w+\b", message)


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


    # Calculate scores
    spam_score = sum(
        spam_words[word]
        for word in words
    )

    ham_score = sum(
        ham_words[word]
        for word in words
    )


    # Current date and time
    checked_time = datetime.now().strftime(
        "%d %b %Y, %I:%M %p"
    )


    # Detection summary
    summary = (
        f"{len(found_keywords)} suspicious keyword(s) "
        f"and {len(found_links)} link(s) detected."
    )


  
    # Strong spam pattern
    strong_spam_score = 0

    # Prize or reward combined with money
    if (
        ("prize" in words or "reward" in words or "winner" in words)
        and ("money" in words or "cash" in words)
    ):
        strong_spam_score += 3

    # Prize or reward combined with urgency
    if (
        ("prize" in words or "reward" in words or "winner" in words)
        and (
            "today" in words
            or "urgent" in words
            or "limited" in words
        )
    ):
        strong_spam_score += 2

    # Request to open a link with prize or money language
    if (
        "link" in words
        and ("open" in words or "click" in words)
        and (
            "prize" in words
            or "reward" in words
            or "money" in words
            or "cash" in words
        )
    ):
        strong_spam_score += 2

    # Claim / reward pattern
    if (
        ("claim" in words and "reward" in words)
        or ("claim" in words and "prize" in words)
    ):
        strong_spam_score += 2

    # Suspicious link combined with suspicious keywords
    if found_links and found_keywords:
        strong_spam_score += 2

    # Large money amount
    money_pattern = re.findall(r"\b\d{5,}\b", message)

    if money_pattern and any(
        word in words
        for word in [
            "win", "won", "winner", "prize", "cash", "reward"
        ]
    ):
        strong_spam_score += 3



    # Spam detection
    if (
        spam_score > ham_score
        or
        strong_spam_score >= 3
    ):

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
            "Avoid clicking unknown links or sharing "
            "personal information."
        )

        alternative = (
            "Please verify the sender and offer through "
            "an official source before taking any action."
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
            "No major safety concern detected. "
            "Still verify unknown senders."
        )

        alternative = (
            "This message can be shared normally "
            "if you trust the sender."
        )

   
    # Save message permanently in database
    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO history (
            message, result, reason, suggestion, alternative,
            keywords, links, time, risk, summary, user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        message,
        result,
        reason,
        suggestion,
        alternative,
        ", ".join(found_keywords),
        ", ".join(found_links),
        checked_time,
        risk_level,
        summary,
        session["user_id"]
    ))

    conn.commit()

    # Load saved messages for the current user
    cursor.execute("""
        SELECT message, result, reason, suggestion, alternative,
               keywords, links, time, risk, summary
        FROM history
        WHERE user_id = ?
        ORDER BY id ASC
    """, (session["user_id"],))

    rows = cursor.fetchall()
    conn.close()

    user_history = []

    for row in rows:
        user_history.append({
            "message": row[0],
            "result": row[1],
            "reason": row[2],
            "suggestion": row[3],
            "alternative": row[4],
            "keywords": [
                w.strip() for w in (row[5] or "").split(",")
                if w.strip()
            ],
            "links": [
                link.strip() for link in (row[6] or "").split(",")
                if link.strip()
            ],
            "time": row[7],
            "risk": row[8],
            "summary": row[9]
        })

    # Dashboard statistics
    total_checked = len(user_history)

    spam_detected = sum(
        1 for item in user_history
        if "SPAM MESSAGE" in item["result"]
        and "NOT SPAM" not in item["result"]
    )

    genuine_detected = sum(
        1 for item in user_history
        if "GENUINE" in item["result"]
    )

    spam_rate = round(
        spam_detected * 100 / total_checked, 1
    ) if total_checked else 0

    # Bar chart statistics
    prize_count = 0
    money_count = 0
    offer_count = 0
    verification_count = 0
    link_count = 0
    urgent_count = 0

    for item in user_history:
        keywords = [w.lower() for w in item["keywords"]]

        if any(w in keywords for w in ["prize", "reward", "winner"]):
            prize_count += 1

        if any(w in keywords for w in ["cash", "money"]):
            money_count += 1

        if any(w in keywords for w in ["offer", "free"]):
            offer_count += 1

        if any(w in keywords for w in ["account", "verify", "verification"]):
            verification_count += 1

        if item["links"]:
            link_count += 1

        if "urgent" in keywords:
            urgent_count += 1

    return render_template(
        "index.html",
        result=result,
        total_checked=total_checked,
        spam_detected=spam_detected,
        genuine_detected=genuine_detected,
        spam_rate=spam_rate,
        history=user_history,
        prize_count=prize_count,
        money_count=money_count,
        offer_count=offer_count,
        verification_count=verification_count,
        link_count=link_count,
        urgent_count=urgent_count
    ) 
   

# Spam details page

@app.route("/spam-details")
def spam_details():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("history.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT message, result, reason, suggestion, alternative,
               keywords, links, time, risk, summary
        FROM history
        WHERE user_id = ?
        AND result LIKE '%SPAM MESSAGE%'
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],))

    row = cursor.fetchone()
    conn.close()

    if row:
        data = dict(row)
        data["keywords"] = (
            data["keywords"].split(",")
            if data["keywords"] else []
        )
        data["links"] = (
            data["links"].split(",")
            if data["links"] else []
        )
        return render_template("spam_details.html", data=data)

    return redirect(url_for("home"))



# Genuine details page
@app.route("/genuine-details")
def genuine_details():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("history.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT message, result, reason, suggestion, alternative,
               keywords, links, time, risk, summary
        FROM history
        WHERE user_id = ?
        AND result LIKE '%NOT SPAM / GENUINE MESSAGE%'
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],))

    row = cursor.fetchone()
    conn.close()

    if row:
        data = dict(row)
        data["keywords"] = (
            data["keywords"].split(",") if data["keywords"] else []
        )
        data["links"] = (
            data["links"].split(",") if data["links"] else []
        )

        return render_template(
            "genuine_details.html",
            data=data
        )

    return redirect(url_for("home"))


# Start Flask
if __name__ == "__main__":
    app.run(debug=True)