---
title: Projects: FAQ chatbot and a Tamil and English text classifier
summary: Build a chatbot that finds the best FAQ answer by TF-IDF similarity, and a classifier that tells Tamil, English and Tanglish text apart with character n-grams.
takeaways:
- A simple retrieval chatbot matches the question to the closest FAQ with TF-IDF and cosine similarity
- A confidence threshold lets the bot say "I do not know" instead of guessing
- Character n-grams work across languages and spelling styles, where word lists fail
---
## Project 1: an FAQ chatbot

A college wants a bot that answers common questions. **Retrieval** is the simplest reliable design: the bot does not invent answers; it finds the closest question you have already answered.

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

faq = [
    ("How do I reset my password?", "Click 'Forgot password' on the login page and follow the email link."),
    ("How can I download my certificate?", "Open My Dashboard, then Certificates, and press Download."),
    ("What are the fees for the course?", "Fees depend on the plan. Open Plans to see the current prices."),
    ("How do I contact support?", "Email support from the Help page. We reply within one working day."),
    ("Can I get a refund?", "Refunds are possible within 7 days if less than 20% of the course is used."),
    ("How long does the course take?", "Most learners finish in 8 to 12 weeks, studying 5 hours a week."),
]
questions = [q for q, _ in faq]
answers = [a for _, a in faq]

vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
question_vectors = vectorizer.fit_transform(questions)

def answer(user_question, threshold=0.2):
    scores = cosine_similarity(vectorizer.transform([user_question]), question_vectors)[0]
    best = int(scores.argmax())
    if scores[best] < threshold:
        return "Sorry, I am not sure. Please contact support.", float(scores[best])
    return answers[best], float(scores[best])

for q in ["forgot my password", "where do I get my certificate", "how much does it cost", "tell me a joke"]:
    reply, score = answer(q)
    print(f"Q: {q}\nA: {reply}  (similarity {score:.2f})\n")
```

```output
Q: forgot my password
A: Click 'Forgot password' on the login page and follow the email link.  (similarity 0.58)

Q: where do I get my certificate
A: Open My Dashboard, then Certificates, and press Download.  (similarity 0.58)

Q: how much does it cost
A: Most learners finish in 8 to 12 weeks, studying 5 hours a week.  (similarity 0.46)

Q: tell me a joke
A: Sorry, I am not sure. Please contact support.  (similarity 0.00)
```

The bot finds the right FAQ for the first two questions, and for "tell me a joke" its similarity is 0.00, below the threshold, so it **admits it does not know** instead of guessing. That honesty is what makes a bot trustworthy.

But look at the third question. "How much does it cost" means the same as "What are the fees for the course?", yet the two share no important words, so the bot matched the wrong FAQ (course duration) with a similarity of 0.46. **A confident wrong answer is worse than "I am not sure".** This is the weakness of word matching: it cannot see that "cost" means "fees". Raising the threshold to 0.5 would stop this one, but tuning on four test questions proves little, so test with many real questions. The real fix is **sentence embeddings**, which match meaning, not words:

```py
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")
question_vectors = model.encode(questions)
scores = cosine_similarity(model.encode(["how much does it cost"]), question_vectors)[0]
```

### Improving the chatbot

| Step | Why |
| --- | --- |
| add several phrasings for each question | more ways to match |
| tune the threshold using real user questions | balance wrong answers against "I do not know" |
| log questions the bot could not answer | they show what FAQs are missing |
| hand over to a human when unsure | trust |
| use an LLM with retrieval (RAG) for natural replies | friendlier answers grounded in your FAQ |

## Project 2: Tamil, English and Tanglish

Learners in Tamil Nadu write in **three** ways: English, Tamil script, and **Tanglish** (Tamil written in English letters). We build a classifier that tells them apart. Word lists would not work well, but **character n-grams** (short runs of letters) do, whatever the language.

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import make_pipeline

samples = [
    ("I want to join the course", "english"), ("what is the fee for this class", "english"), ("please send me the certificate", "english"),
    ("when does the next batch start", "english"), ("the video is not playing", "english"), ("thank you for your help", "english"),
    ("நான் இந்த படிப்பில் சேர விரும்புகிறேன்", "tamil"), ("இந்த வகுப்பின் கட்டணம் என்ன", "tamil"), ("எனக்கு சான்றிதழ் அனுப்புங்கள்", "tamil"),
    ("அடுத்த பேட்ச் எப்போது தொடங்கும்", "tamil"), ("வீடியோ ஓடவில்லை", "tamil"), ("உங்கள் உதவிக்கு நன்றி", "tamil"),
    ("naan intha course la sera virumburen", "tanglish"), ("intha class ku fees evlo", "tanglish"), ("enakku certificate anuppunga", "tanglish"),
    ("adutha batch eppo start aagum", "tanglish"), ("video odala sir", "tanglish"), ("ungal udhavikku nandri", "tanglish"),
]
texts = [t for t, _ in samples]
labels = [l for _, l in samples]

model = make_pipeline(TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4)), LogisticRegression(max_iter=1000))
scores = cross_val_score(model, texts, labels, cv=3)
print("cross-validated accuracy:", round(float(scores.mean()), 2))

model.fit(texts, labels)
for text in ["enna fees sir", "எனக்கு உதவி வேண்டும்", "please help me with the login", "video load aagala"]:
    print(f"{model.predict([text])[0]:<9} <- {text}")
```

```output
cross-validated accuracy: 0.94
tanglish  <- enna fees sir
tamil     <- எனக்கு உதவி வேண்டும்
english   <- please help me with the login
tanglish  <- video load aagala
```

Character n-grams pick up the **look** of each writing style: Tamil script uses entirely different characters, and Tanglish has its own spelling habits ("aagum", "sir"). That is why this works with so little data. The Tamil and Tanglish samples here are a small illustration written for this lesson; for a real product, collect many more examples from real users.

### Going further with Indian languages

| Need | Tools |
| --- | --- |
| language identification | `langdetect`, `fastText` language models |
| Tamil text tokenisation and models | the **IndicNLP** library, **AI4Bharat** models (IndicBERT) |
| multilingual understanding | multilingual transformers (mBERT, XLM-RoBERTa, MuRIL) |
| transliteration (Tanglish to Tamil) | `indic-transliteration` and similar libraries |
| speech | Whisper supports Tamil transcription |

:::warning
Models trained mostly on English perform noticeably worse on Tamil, and especially on Tanglish with its inconsistent spelling. Test on **real examples from your own users** before you trust any score, and include all three writing styles in your test data.
:::

:::practice capstone-project
Ask the Capstone Project agent to help you scope one of these two projects: which data would you collect, and how would you test the bot with real learners?
:::
