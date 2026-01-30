import streamlit as st
from utils import storage
from sidebar import render_sidebar
import openai
import random
import json
from pathlib import Path

# -----------------------------
# Page setup (Japanese UI)
# -----------------------------
st.set_page_config(page_title="日本語コーチ（会話）", page_icon="💬", layout="wide")

st.title("💬 日本語コーチ（会話）")
st.write("日本語で会話練習しましょう。まずは **N3の復習（思い出して使える状態）** を最優先に、次に **ビジネス日本語** を強化します。")
st.write("わからない時は、**「わからない」「やさしい日本語で」** と言ってください。やさしい日本語で説明します。")
st.write("右のサイドバーで語彙を追加できます。『📝 クイズ』で語彙クイズも出せます。")

# -----------------------------
# Load Configuration
# -----------------------------
config_path = Path("utils/config.json")
config = {}
if config_path.exists():
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

OPENAI_MODEL = config.get("openai_model_name", "gpt-4.1")
DEFAULT_TEMPERATURE = float(config.get("temperature", 0.7))

# If your config uses learning_language, prefer it; else fall back to language.
LANGUAGE = config.get("learning_language", config.get("language", "Japanese"))

# -----------------------------
# Sidebar (navigation + settings)
# -----------------------------
render_sidebar()
st.sidebar.header("⚙️ 設定")

mode = st.sidebar.radio(
    "モードを選んでください",
    ["N3リコール（文法・語彙）", "ビジネス（会議・メール）", "雑談（ナチュラル会話）"],
    index=0,
)

# Temperature settings by mode
if mode == "N3リコール（文法・語彙）":
    temperature = 0.3
elif mode == "ビジネス（会議・メール）":
    temperature = 0.6
else:
    temperature = DEFAULT_TEMPERATURE  # typically 0.7–0.8

st.sidebar.caption(f"モデル: {OPENAI_MODEL}")
st.sidebar.caption(f"Temperature: {temperature}")

# -----------------------------
# System prompt (customized for you)
# -----------------------------
BASE_SYSTEM_PROMPT = """
あなたは「日本語コーチ兼ビジネス日本語の相手役」です。
ユーザーはJLPT N3合格済みだが忘れかけている。1か月後に日本企業のクライアントと対面・会議・メール・雑談が必要。
最優先はN3範囲の知識を“思い出して使える状態”に戻すこと。その後ビジネス日本語へ伸ばす。

# 基本ルール
- 原則、日本語で話す（丁寧だがフレンドリー）。
- ユーザーが「わからない」「もう少しやさしく」「意味は？」と言ったら、必ず「やさしい日本語」で言い換えて説明する。
- 英語説明は、ユーザーが求めた場合のみ。
- 返答は短め→会話を続ける質問で終える（実戦練習を優先）。

# 学習モード（この会話では次のモード）
{MODE_LINE}

# 添削フォーマット（ユーザーの日本語がある場合は必ず）
1) ✅ 自然な日本語（修正版）
2) 🔎 ポイント（1〜2行：助詞/語彙/敬語/語順）
3) 🧠 ミニ説明（やさしい日本語で）
4) 🔁 もう一回：短い言い直しを求める質問

# ロールプレイ
ユーザーが「会議」「メール」「名刺交換」「雑談」「電話」などと言ったら、その場面で相手役になり、短いターンで進める。
"""

if mode == "N3リコール（文法・語彙）":
    MODE_LINE = """- N3リコール優先：
  - N3文法・助詞・活用・よく使う語彙を中心に、ミスを直しながら反復。
  - 1回の返信で「学び + もう一度言わせる」を必ず入れる。
  - 可能なら「同じ意味で別の言い方」も1つ提案する。"""
elif mode == "ビジネス（会議・メール）":
    MODE_LINE = """- ビジネス日本語：
  - 会議・メール・挨拶・依頼・お詫び・確認・フォローアップを実戦形式で練習。
  - 敬語（丁寧語/謙譲語/尊敬語）を場面に合わせて指導。
  - メールは「件名→本文→締め」の型で、自然な表現に直す。"""
else:
    MODE_LINE = """- 雑談（ナチュラル会話）：
  - 自然な会話を続ける。必要に応じて軽く添削し、より自然な言い方も提案。
  - 聞き返し表現（例: もう一度お願いします／つまり〜ですか？）も教える。"""

SYSTEM_PROMPT = BASE_SYSTEM_PROMPT.format(MODE_LINE=MODE_LINE)

# -----------------------------
# OpenAI helper
# -----------------------------
def get_ai_response(messages):
    """
    messages: chat history WITHOUT system prompt.
    We'll prepend SYSTEM_PROMPT each time to ensure consistent behavior.
    """
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    payload = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=payload,
        temperature=temperature,
    )
    return response.choices[0].message.content


# -----------------------------
# Initialize chat history
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Friendly Japanese greeting
    st.session_state.messages.append({
        "role": "assistant",
        "content": "こんにちは！😊 まずはN3の復習から始めましょう。\n最近いちばん困るのは「会議」「メール」「雑談」のどれですか？"
    })


# -----------------------------
# Vocabulary panel (same functionality as before)
# -----------------------------
st.sidebar.header("📖 単語（あなたの語彙）")

vocab_list = storage.load_vocabulary()

# Normalize vocab entries into dicts
corrected_vocab_list = []
for entry in vocab_list:
    if isinstance(entry, str):
        corrected_vocab_list.append({"word": entry, "translation": "None.", "example": "None."})
    elif isinstance(entry, dict):
        corrected_vocab_list.append({
            "word": entry.get("word", "Unknown"),
            "translation": entry.get("translation", "None."),
            "example": entry.get("example", "None."),
        })

if corrected_vocab_list != vocab_list:
    storage.save_vocabulary(corrected_vocab_list)

vocab_list = corrected_vocab_list

new_word = st.sidebar.text_input("➕ 新しい単語を追加", key="new_vocab_word")

if st.sidebar.button("追加"):
    if new_word.strip() and all(w["word"] != new_word.strip() for w in vocab_list):
        client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

        prompt = f"""
あなたは日本語教師です。単語「{new_word}」について次を出してください：
1) 英語の短い意味
2) 日本語の例文（できればビジネス寄りもOK）

次の形式で：
Translation: <英語>
Example: <日本語例文>
        """.strip()

        with st.spinner(f"『{new_word}』の意味と例文を作成中..."):
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )

        content = response.choices[0].message.content
        translation, example = "", ""

        for line in content.splitlines():
            if line.strip().startswith("Translation:"):
                translation = line.replace("Translation:", "").strip()
            elif line.strip().startswith("Example:"):
                example = line.replace("Example:", "").strip()

        if translation and example:
            vocab_list.append({"word": new_word.strip(), "translation": translation, "example": example})
            storage.save_vocabulary(vocab_list)
            st.sidebar.success(f"追加しました: {new_word.strip()}")
            st.experimental_rerun()
        else:
            st.sidebar.error("意味と例文の取得に失敗しました。もう一度試してください。")

if vocab_list:
    for word_entry in vocab_list:
        st.sidebar.markdown(f"- **{word_entry['word']}**")
else:
    st.sidebar.write("まだ単語がありません。")

# -----------------------------
# Quiz button (from your vocab)
# -----------------------------
if st.sidebar.button("📝 クイズ"):
    if len(vocab_list) < 1:
        st.sidebar.warning("単語を1つ以上追加してください。")
    else:
        quiz_words = random.sample(vocab_list, min(10, len(vocab_list)))
        quiz_word_list = [w["word"] for w in quiz_words]

        quiz_prompt = f"""
あなたは日本語教師です。次の単語を使って、学習者向けのミニクイズを作ってください：
{', '.join(quiz_word_list)}

条件：
- N3レベル中心（必要なら少し上でもOK）
- 3〜6問
- 最後に解答もつける
""".strip()

        with st.spinner("クイズを作成中..."):
            quiz_response = get_ai_response(st.session_state.messages + [{"role": "user", "content": quiz_prompt}])

        st.session_state.messages.append({"role": "assistant", "content": quiz_response})

# -----------------------------
# Quick buttons (easy Japanese + drill shortcuts)
# -----------------------------
st.subheader("🚀 クイックボタン（すぐ練習）")
c1, c2, c3, c4, c5, c6 = st.columns(6)

if c1.button("やさしい日本語で"):
    st.session_state.messages.append({"role": "user", "content": "今の説明を、もっとやさしい日本語で短く説明してください。"})
if c2.button("例文3つ"):
    st.session_state.messages.append({"role": "user", "content": "今のポイントの例文を3つください。（やさしい→ふつう→ビジネス）"})
if c3.button("敬語チェック"):
    st.session_state.messages.append({"role": "user", "content": "私の文をビジネスで自然な敬語に直して、理由もやさしい日本語で説明してください。"})
if c4.button("N3ミニクイズ"):
    st.session_state.messages.append({"role": "user", "content": "JLPT N3のミニクイズを3問ください（助詞・活用・文法）。答え合わせもしてください。"})
if c5.button("メール練習"):
    st.session_state.messages.append({"role": "user", "content": "ビジネスメールの練習をしたいです。状況を設定して、私にメールを書かせてください。"})
if c6.button("会議ロールプレイ"):
    st.session_state.messages.append({"role": "user", "content": "会議のロールプレイをしたいです。あなたは日本のクライアント役で、短いターンで進めてください。"})


# -----------------------------
# Display chat history
# -----------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# -----------------------------
# Chat input
# -----------------------------
user_input = st.chat_input("ここに入力してください（日本語でOK）")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.write(user_input)

    with st.spinner("考え中..."):
        bot_reply = get_ai_response(st.session_state.messages)

    with st.chat_message("assistant"):
        st.write(bot_reply)

    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
