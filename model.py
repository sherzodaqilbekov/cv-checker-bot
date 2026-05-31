import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
import re
import pickle

# 1. Ma'lumotlarni yuklash
print("📂 Dataset yuklanmoqda...")
df = pd.read_csv('UpdatedResumeDataSet.csv')
print(f"✅ Jami: {len(df)} ta CV topildi")
print(f"📊 Kategoriyalar: {df['Category'].nunique()} ta")
print(df['Category'].value_counts())

# 2. Ma'lumotlarni tozalash
print("\n🧹 Ma'lumotlar tozalanmoqda...")

def clean_text(text):
    text = re.sub(r'http\S+', '', text)        # linklarni o'chirish
    text = re.sub(r'[^a-zA-Z\s]', '', text)    # raqam va belgilarni o'chirish
    text = text.lower()                         # kichik harfga o'tkazish
    text = re.sub(r'\s+', ' ', text).strip()   # ortiqcha bo'shliqlarni o'chirish
    return text

df['Clean_Resume'] = df['Resume'].apply(clean_text)
print("✅ Tozalash tugadi!")

# 3. Train/Test ga ajratish (80/20)
print("\n✂️ Ma'lumotlar bo'linmoqda (80% train, 20% test)...")
X = df['Clean_Resume']
y = df['Category']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"✅ Train: {len(X_train)} ta")
print(f"✅ Test: {len(X_test)} ta")

# 4. TF-IDF Vectorizer
print("\n🔢 TF-IDF hisablanmoqda...")
vectorizer = TfidfVectorizer(max_features=1500, stop_words='english')
X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)
print("✅ Tayyor!")

# 5. Model o'qitish
print("\n🤖 Model o'qitilmoqda...")
model = LogisticRegression(max_iter=1000)
model.fit(X_train_vec, y_train)
print("✅ Model o'qitildi!")

# 6. Test qilish
print("\n📊 Model sinovdan o'tkazilmoqda...")
y_pred = model.predict(X_test_vec)
accuracy = accuracy_score(y_test, y_pred)
print(f"\n🎯 Model aniqligi: {accuracy*100:.2f}%")
print("\n📋 Batafsil natija:")
print(classification_report(y_test, y_pred))

# 7. Modelni saqlash
print("\n💾 Model saqlanmoqda...")
with open('resume_model.pkl', 'wb') as f:
    pickle.dump(model, f)
with open('vectorizer.pkl', 'wb') as f:
    pickle.dump(vectorizer, f)
print("✅ Model saqlandi: resume_model.pkl")

# 8. Test - yangi CV ni tekshirish
print("\n🧪 Yangi CV tekshirilmoqda...")

test_cv = """
Python Developer with 3 years of experience.
Skills: Python, Django, Flask, SQL, REST API, Git
Education: Bachelor of Computer Science
Experience: Developed web applications, worked with databases
"""

test_clean = clean_text(test_cv)
test_vec = vectorizer.transform([test_clean])
prediction = model.predict(test_vec)
print(f"📄 CV kategoriyasi: {prediction[0]}")