import csv
import math
from collections import Counter

# Read dataset
messages = []
labels = []

with open("dataset/spam.csv", "r", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    for row in reader:
        messages.append(row["message"].lower())
        labels.append(row["label"])

# Count words
spam_words = Counter()
ham_words = Counter()

for message, label in zip(messages, labels):
    words = message.split()

    if label == "spam":
        spam_words.update(words)
    else:
        ham_words.update(words)

print("Model trained successfully!")