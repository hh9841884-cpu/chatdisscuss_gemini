import streamlit as st
import os
from dotenv import load_dotenv
import google.generativeai as genai
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import av
import openai

# .env 読み込み
load_dotenv()

# APIキー
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Gemini API 設定
genai.configure(api_key=GEMINI_API_KEY)

# OpenAI API 設定
openai.api_key = OPENAI_API_KEY

st.title("🔥 魔王軍 入団面接（音声入力対応）")

# --- ゲームモード選択 ---
mode = st.selectbox("ゲームモードを選択", ["論破度判定"])

# --- 論破度モードのときだけキャラクター選択 ---
character = None
if mode == "論破度判定":
    character = st.selectbox("場面を選択", ["魔王軍入団面接"])

# --- セッション状態の初期化 ---
if "turn" not in st.session_state:
    st.session_state.turn = 0
if "history" not in st.session_state:
    st.session_state.history = []
if "finished" not in st.session_state:
    st.session_state.finished = False
if "intro_shown" not in st.session_state:
    st.session_state.intro_shown = False

# --- チャット履歴の表示（魔王は画像つき） ---
for msg in st.session_state.history:
    if msg["role"] == "assistant":
        with st.chat_message("assistant"):
            st.image("maou.jpeg", width=80)
            st.write(msg["content"])
    else:
        with st.chat_message("user"):
            st.write(msg["content"])

# --- 魔王軍入団面接の最初のメッセージ ---
if (
    mode == "論破度判定"
    and character == "魔王軍入団面接"
    and not st.session_state.intro_shown
):
    intro = "🔥 **魔王軍 入団面接を開始する…**\n魔王：『まずは名を名乗れ。貴様は何者だ？』"
    st.session_state.history.append({"role": "assistant", "content": intro})
    st.session_state.intro_shown = True
    st.session_state.turn = 1
    st.rerun()

# --- 音声入力（録音） ---
st.subheader("🎤 音声で回答する場合はこちら")

def audio_frame_callback(frame):
    sound = frame.to_ndarray()
    return av.AudioFrame.from_ndarray(sound, layout="mono")

webrtc_ctx = webrtc_streamer(
    key="speech",
    mode=WebRtcMode.SENDONLY,
    audio_receiver_size=1024,
    media_stream_constraints={"audio": True, "video": False},
)

audio_text = None

if webrtc_ctx and webrtc_ctx.audio_receiver:
    audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
    if audio_frames:
        with open("input.wav", "wb") as f:
            f.write(audio_frames[0].to_ndarray().tobytes())

        try:
            with open("input.wav", "rb") as f:
                transcript = openai.Audio.transcribe("whisper-1", f)
                audio_text = transcript["text"]
                st.write("📝 音声認識結果:", audio_text)
        except:
            pass

# --- テキスト入力 ---
text_input = st.chat_input("メッセージを入力")

# 音声があれば優先
user_input = audio_text if audio_text else text_input

# --- 入力処理 ---
if user_input and not st.session_state.finished:

    st.session_state.history.append({"role": "user", "content": user_input})
    st.session_state.turn += 1

    if st.session_state.turn <= 10 and not st.session_state.finished:

        system_prompt = f"""
あなたは魔王として振る舞う。
ユーザーは魔王軍に入りたい志願者である。
あなたは面接官として、ユーザーに質問を投げかける。
質問は短く鋭く、魔王らしい威圧感を持たせる。
返答は「質問のみ」にする。

現在のターン: {st.session_state.turn}

もし次の質問が最後の質問（ターン10）であれば、
必ず質問文の冒頭に「これが最後の質問だ…」と付け加える。
"""

        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            [
                {"role": "user", "parts": [system_prompt]},
                *[
                    {"role": msg["role"], "parts": [msg["content"]]}
                    for msg in st.session_state.history
                ]
            ]
        )

        ai_reply = response.text
        st.session_state.history.append({"role": "assistant", "content": ai_reply})

    if st.session_state.turn >= 3 and not st.session_state.finished:

        eval_prompt = """
あなたは魔王として、志願者の回答を100点満点で評価する。
平均で60点になるように厳しめに評価すること。
75点以上で合格とする。

評価基準（各25点満点）：
1. 魔王軍にふさわしい野心（0〜25）
2. 忠誠心（0〜25）
3. 戦闘力のアピール（0〜25）
4. 論理性と説得力（0〜25）

あなたは以下を判断する：
1. 志願者の回答が評価に十分な情報を含んでいるか？
2. もし十分なら即座に評価を行う。
3. もし不十分なら「False」とだけ返す。
"""

        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            [
                {"role": "user", "parts": [eval_prompt]},
                *[
                    {"role": msg["role"], "parts": [msg["content"]]}
                    for msg in st.session_state.history
                ]
            ]
        )

        result = response.text.strip()

        if result != "False":
            st.session_state.history.append({"role": "assistant", "content": result})
            st.session_state.finished = True

        elif st.session_state.turn >= 10:
            final_eval_prompt = """
あなたは魔王として、志願者の回答を100点満点で評価する。
75点以上で合格とする。

評価基準（各25点満点）：
1. 魔王軍にふさわしい野心（0〜25）
2. 忠誠心（0〜25）
3. 戦闘力のアピール（0〜25）
4. 論理性と説得力（0〜25）
"""

            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(
                [
                    {"role": "user", "parts": [final_eval_prompt]},
                    *[
                        {"role": msg["role"], "parts": [msg["content"]]}
                        for msg in st.session_state.history
                    ]
                ]
            )

            final_result = response.text
            st.session_state.history.append({"role": "assistant", "content": final_result})
            st.session_state.finished = True

    st.rerun()

# --- ゲーム終了後の案内 ---
if st.session_state.finished:
    st.info("面接は終了しました。もう一度プレイするには下のボタンを押してください。")

    if st.button("もう一度プレイする"):
        st.session_state.turn = 0
        st.session_state.history = []
        st.session_state.finished = False
        st.session_state.intro_shown = False
        st.rerun()
