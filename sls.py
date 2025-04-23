import streamlit as st
import openai
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import random
import json
from streamlit_autorefresh import st_autorefresh

# ──────────────────────────────
# ✅ 기본 설정
# ──────────────────────────────
api_keys = st.secrets["api"]["keys"]
selected_api_key = random.choice(api_keys)
client = openai.OpenAI(api_key=selected_api_key)
assistant_id = 'asst_Uoh3TfssVpHXcrpbrqXDDlqv'

# 페이지 구성
st.set_page_config(page_title="학생용 가사 생성", layout="wide")

# 제작자 이름 
st.caption("웹 어플리케이션 문의사항은 정재환(서울창일초), woghks0524jjh@gmail.com, 010-3393-0283으로 연락주세요.")

if "conversation" not in st.session_state:
    st.session_state["conversation"] = []
if "usingthread" not in st.session_state:
    new_thread = client.beta.threads.create()
    st.session_state["usingthread"] = new_thread.id
if "status" not in st.session_state:
    st.session_state["status"] = "idle"
if "starter_message_shown" not in st.session_state:
    st.session_state["starter_message_shown"] = False

# ──────────────────────────────
# ✅ 사이드바: 정보 입력
# ──────────────────────────────
with st.sidebar:
    st.header("📝 기본 정보")
    code = st.text_input("🔑 코드", key="code")
    student_name = st.text_input("🧒 이름", key="name")
    conversation_title = st.text_input("🎵 노래 제목", key="title")

# ──────────────────────────────
# ✅ 자동 새로고침 (승인 대기 중)
# ──────────────────────────────
if st.session_state["status"] == "waiting_for_approval":
    st_autorefresh(interval=10000, key="refresh")

# ──────────────────────────────
# ✅ 시트 접근 함수
# ──────────────────────────────
def get_sheet():
    credentials_dict = json.loads(st.secrets["gcp"]["credentials"])
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(credentials)
    return gc.open(st.secrets["google"]["lyrics"]).sheet1

sheet = get_sheet()
data = sheet.get_all_records()

# ──────────────────────────────
# ✅ 승인 여부 확인
# ──────────────────────────────
approved = False
latest_answer = None

for row in reversed(data):
    if (row["코드"] == code and
        row["이름"] == student_name and
        row["요청"] == st.session_state.get("latest_question")):
        approved = row["승인여부"].upper() == "TRUE"
        latest_answer = row["가사"]
        break

if approved and latest_answer:
    if ("assistant", latest_answer) not in st.session_state["conversation"]:
        st.session_state["conversation"].append(("assistant", latest_answer))
        st.session_state["status"] = "idle"
        st.rerun()

# ──────────────────────────────
# ✅ 대화 화면
# ──────────────────────────────
st.title("🎹 생성형AI 가사 만들기")
st.subheader("📚 대화 내용")

if not st.session_state["starter_message_shown"]:
    st.session_state["conversation"].insert(0, (
        "assistant", "만들고 싶은 노래 가사를 적어주세요. 느낌, 스타일, 형식 등 자세하게 입력해주세요."
    ))
    st.session_state["starter_message_shown"] = True

with st.container(height=500, border=True):
    for role, msg in st.session_state["conversation"]:
        if role == "user":
            st.chat_message("user").write(msg)
        elif role == "assistant":
            st.chat_message("assistant").write(msg)

# ──────────────────────────────
# ✅ 입력 및 처리
# ──────────────────────────────
question = st.chat_input("✍️ 요청사항을 입력해보세요")

if question:
    st.session_state["conversation"].append(("user", question))
    st.session_state["status"] = "waiting_for_approval"

    # GPT 프롬프트
    system_prompt = f"""
    노래 제목: {conversation_title}

    사용자가 다음과 같이 요청했어요:
    \"{question}\"
    요청한 내용을 반영하여 가사를 생성해주세요.
    """

    client.beta.threads.messages.create(
        thread_id=st.session_state["usingthread"],
        role="user",
        content=system_prompt)

    run = client.beta.threads.runs.create(
        thread_id=st.session_state["usingthread"],
        assistant_id=assistant_id)

    while True:
        run = client.beta.threads.runs.retrieve(
            thread_id=st.session_state["usingthread"],
            run_id=run.id)
        if run.status == "completed":
            break
        time.sleep(2)

    response = client.beta.threads.messages.list(st.session_state["usingthread"])
    msg = response.data[0].content[0].text.value

    # 저장
    st.session_state["latest_answer"] = msg
    st.session_state["latest_question"] = question

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = [
        code,
        student_name,
        question,
        msg,
        "FALSE",
        now
    ]
    sheet.append_row(new_row)
    st.rerun()

# ──────────────────────────────
# ✅ 승인 대기 중 안내
# ──────────────────────────────
if st.session_state["status"] == "waiting_for_approval":
    st.info("⏳ 선생님이 가사를 확인 중이에요. 잠시만 기다려 주세요.")
