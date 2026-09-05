import json
import os
import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader

# Page setup
st.set_page_config(page_title="AI Quiz Generator", page_icon="📝", layout="wide")

# Initialize Session State
if "quiz_data" not in st.session_state:
    st.session_state["quiz_data"] = None
if "quiz_submitted" not in st.session_state:
    st.session_state["quiz_submitted"] = False
if "user_answers" not in st.session_state:
    st.session_state["user_answers"] = {}
if "short_evaluations" not in st.session_state:
    st.session_state["short_evaluations"] = {}

# Fetch API Key
api_key = ""
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
elif "GEMINI_API_KEY" in os.environ:
    api_key = os.environ["GEMINI_API_KEY"]

if not api_key:
    api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

api_key = api_key.strip().strip('"').strip("'") if api_key else ""

if not api_key:
    st.info("👈 Please enter your Gemini API Key in the sidebar or configure it in Streamlit Secrets to continue.")
    st.stop()

try:
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Failed to configure Gemini Client: {e}")
    st.stop()

def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text

def generate_quiz(text, num_questions, difficulty, q_type):
    model = genai.GenerativeModel('gemini-3.6-flash')
    
    prompt = f"""
    Based on the following context, generate a {num_questions}-question quiz.
    Difficulty Level: {difficulty}
    Question Type: {q_type}

    Context:
    {text[:8000]}

    Return ONLY a valid JSON array of objects with keys: "question", "options" (array if MCQ/TF, empty list if short answer), "answer", "explanation".
    """
    
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

def evaluate_short_answer(question, expected_answer, user_answer):
    model = genai.GenerativeModel('gemini-3.6-flash')
    prompt = f"""
    Question: {question}
    Expected Key Concepts: {expected_answer}
    Student Answer: {user_answer}

    Grade the student's answer. Return ONLY a valid JSON object with keys:
    - "is_correct": true or false
    - "feedback": "Brief 1-2 sentence feedback explaining why it's correct or what was missed."
    """
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

# App UI
st.title("📝 AI Study Quiz Generator")

uploaded_file = st.file_uploader("Upload Study Material (PDF)", type=["pdf"])

if uploaded_file:
    with st.spinner("Extracting text from PDF..."):
        pdf_text = extract_text_from_pdf(uploaded_file)
    st.success("PDF processed successfully!")

    st.sidebar.header("Quiz Settings")
    num_q = st.sidebar.slider("Number of Questions", min_value=1, max_value=20, value=5)
    difficulty = st.sidebar.selectbox("Difficulty Level", ["Easy", "Medium", "Hard"])
    q_type = st.sidebar.selectbox("Question Type", ["Multiple Choice (MCQs)", "True/False", "Short Questions"])

    if st.button("Generate Quiz"):
        with st.spinner("Generating quiz with Gemini..."):
            try:
                st.session_state["quiz_data"] = generate_quiz(pdf_text, num_q, difficulty, q_type)
                st.session_state["quiz_submitted"] = False
                st.session_state["user_answers"] = {}
                st.session_state["short_evaluations"] = {}
                st.rerun()
            except Exception as e:
                st.error(f"Error generating quiz: {e}")

# Render Quiz Section
if st.session_state["quiz_data"]:
    quiz = st.session_state["quiz_data"]

    # MODE 1: Answering Quiz
    if not st.session_state["quiz_submitted"]:
        st.header("🎯 Take Quiz")
        
        with st.form("quiz_input_form"):
            for idx, q in enumerate(quiz):
                st.subheader(f"Q{idx+1}: {q['question']}")
                
                # index=None forces radio buttons to start completely unselected
                if "options" in q and q["options"]:
                    selected_val = st.radio(
                        f"Select your answer for Q{idx+1}:",
                        q["options"],
                        index=None,
                        key=f"user_q_{idx}"
                    )
                    st.session_state["user_answers"][idx] = selected_val
                else:
                    input_val = st.text_area(
                        f"Write your answer for Q{idx+1}:",
                        key=f"user_q_{idx}"
                    )
                    st.session_state["user_answers"][idx] = input_val
                st.divider()

            submit_btn = st.form_submit_button("Submit Answers")
            if submit_btn:
                # Validation check: Ensure all questions are answered
                unanswered = [i + 1 for i, ans in st.session_state["user_answers"].items() if ans is None or str(ans).strip() == ""]
                
                if unanswered:
                    st.error(f"Please answer all questions before submitting! Unanswered: Question(s) {', '.join(map(str, unanswered))}")
                else:
                    has_options = "options" in quiz[0] and quiz[0]["options"]
                    if not has_options:
                        with st.spinner("AI is grading your short answers..."):
                            for idx, q in enumerate(quiz):
                                u_ans = st.session_state["user_answers"].get(idx, "")
                                st.session_state["short_evaluations"][idx] = evaluate_short_answer(
                                    q["question"], q["answer"], u_ans
                                )
                    st.session_state["quiz_submitted"] = True
                    st.rerun()

    # MODE 2: Results & Explanations
    else:
        st.header("📊 Quiz Results")
        score = 0
        has_options = "options" in quiz[0] and quiz[0]["options"]

        for idx, q in enumerate(quiz):
            user_ans = st.session_state["user_answers"].get(idx, "No Answer")
            st.write(f"**Q{idx+1}: {q['question']}**")
            
            # Grading MCQs & True/False
            if has_options:
                if str(user_ans).strip().lower() == str(q['answer']).strip().lower():
                    score += 1
                    st.success(f"✅ Your Answer: {user_ans} (Correct!)")
                else:
                    st.error(f"❌ Your Answer: {user_ans} | Correct Answer: {q['answer']}")
                st.caption(f"Explanation: {q.get('explanation', 'N/A')}")
            
            # Short Answer Results
            else:
                eval_res = st.session_state["short_evaluations"].get(idx, {})
                if eval_res.get("is_correct", False):
                    score += 1
                    st.success(f"✅ Your Answer: {user_ans}")
                else:
                    st.error(f"❌ Your Answer: {user_ans}")
                
                st.write(f"**AI Evaluation:** {eval_res.get('feedback', '')}")
                st.info(f"💡 Expected Key Concepts: {q['answer']}")

            st.divider()

        st.balloons()
        st.metric("Final Score", f"{score} / {len(quiz)}")

        if st.button("Retake Quiz"):
            st.session_state["quiz_submitted"] = False
            st.session_state["short_evaluations"] = {}
            st.rerun()
