import json
import os
import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader

# Page setup
st.set_page_config(page_title="AI Quiz Generator", page_icon="📝", layout="wide")

# Fetch API Key cleanly from Secrets or Environment
api_key = ""
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
elif "GEMINI_API_KEY" in os.environ:
    api_key = os.environ["GEMINI_API_KEY"]

# Sidebar fallback if no key is configured in backend
if not api_key:
    api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

# Clean key from accidental whitespace or quotes
api_key = api_key.strip().strip('"').strip("'") if api_key else ""

# Stop execution cleanly if key is missing
if not api_key:
    st.info("👈 Please enter your Gemini API Key in the sidebar or configure it in Streamlit Secrets to continue.")
    st.stop()

# Configure GenAI SDK only when a valid key string exists
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
    # Using the recommended standard model
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    Based on the following context, generate a {num_questions}-question quiz.
    Difficulty Level: {difficulty}
    Question Type: {q_type}

    Context:
    {text[:8000]}

    Return ONLY a valid JSON array of objects with keys: "question", "options" (array if MCQ/TF), "answer", "explanation".
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
                quiz_data = generate_quiz(pdf_text, num_q, difficulty, q_type)
                st.session_state["quiz_data"] = quiz_data
                st.session_state["user_answers"] = {}
                st.session_state["submitted"] = False
            except Exception as e:
                st.error(f"Error generating quiz: {e}")

if "quiz_data" in st.session_state:
    st.header("🎯 Take Quiz")
    quiz = st.session_state["quiz_data"]

    with st.form("quiz_form"):
        for idx, q in enumerate(quiz):
            st.subheader(f"Q{idx+1}: {q['question']}")
            
            if "options" in q and q["options"]:
                user_choice = st.radio(f"Select answer for Q{idx+1}", q["options"], key=f"q_{idx}")
                st.session_state["user_answers"][idx] = user_choice
            else:
                user_text = st.text_input(f"Your Answer for Q{idx+1}", key=f"q_{idx}")
                st.session_state["user_answers"][idx] = user_text

        submit_btn = st.form_submit_button("Submit Quiz")

    if submit_btn:
        st.session_state["submitted"] = True

    if st.session_state.get("submitted", False):
        st.header("📊 Quiz Results")
        score = 0
        
        for idx, q in enumerate(quiz):
            user_ans = st.session_state["user_answers"].get(idx, "")
            st.write(f"**Q{idx+1}: {q['question']}**")
            
            if "options" in q and q["options"]:
                if user_ans == q["answer"]:
                    score += 1
                    st.success(f"Your Answer: {user_ans} (Correct!)")
                else:
                    st.error(f"Your Answer: {user_ans} | Correct Answer: {q['answer']}")
            else:
                st.info(f"Your Answer: {user_ans}")
                st.success(f"Ideal Answer Keywords: {q['answer']}")

            st.caption(f"Explanation: {q.get('explanation', 'N/A')}")
            st.divider()

        if "options" in quiz[0] and quiz[0]["options"]:
            st.balloons()
            st.metric("Final Score", f"{score} / {len(quiz)}")
