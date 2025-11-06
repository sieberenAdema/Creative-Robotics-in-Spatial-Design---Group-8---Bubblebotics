# Training the classifier

# pip install sentence-transformers scikit-learn joblib
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
import json, joblib, numpy as np

# Load your dataset where text is the input and label is the output.
texts, labels = [], []
with open("dataset.jsonl") as f:
    for line in f:
        j = json.loads(line)
        texts.append(j["text"])
        labels.append(j["label"])

# Use a small embedding model to convert text to vectors (no need to train this ourselves)
embedder = SentenceTransformer("all-MiniLM-L6-v2")
X = embedder.encode(texts)
y = np.array(labels)

# Train a classifier with more iterations for better convergence and logistic regression
clf = LogisticRegression(max_iter=1000)
clf.fit(X, y)

# Save both models, the embedder (text to vector) and the classifier (vector to label)
embedder.save("embedder")
joblib.dump(clf, "mode_classifier.pkl")

print("✅ Classifier trained and saved.")
