import json
import os
import streamlit as st
from google import genai
from google.genai import types
from pypdf import PdfReader

# Page setup
st.set_page_config(page_title="AI Quiz Generator", page_icon="📝", layout="wide")

# Initialize Gemini Client
api_key = os.environ.get("GEMINI_API_KEY") or st.sidebar.text_input("Enter Gemini API Key", type="password")

if not api_key:
    st.warning("Please provide a Gemini API Key in the sidebar or setup App Secrets.")
    st.stop()

client = genai.Client(api_key=api_key)

def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text

def generate_quiz(text, num_questions, difficulty, q_type):
    prompt = f"""
    Based on the following context, generate a {num_questions}-question quiz.
    Difficulty Level: {difficulty}
    Question Type: {q_type}

    Context:
    {text[:8000]}  # Limiting text length for API context limit

    Return ONLY a JSON array of objects with the following schema depending on question type:

    For Multiple Choice (MCQs):
    [
      {{
        "question": "Question text",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "answer": "Option A",
        "explanation": "Brief explanation"
      }}
    ]

    For True/False:
    [
      {{
        "question": "Statement text",
        "options": ["True", "False"],
        "answer": "True",
        "explanation": "Brief explanation"
      }}
    ]

    For Short Questions:
    [
      {{
        "question": "Question text",
        "answer": "Key answer keywords or phrase",
        "explanation": "Brief ideal response summary"
      }}
    ]
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
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
            
            if "options" in q:
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
            
            if "options" in q:
                if user_ans == q["answer"]:
                    score += 1
                    st.success(f"Your Answer: {user_ans} (Correct!)")
                else:
                    st.error(f"Your Answer: {user_ans} | Correct Answer: {q['answer']}")
            else:
                st.info(f"Your Answer: {user_ans}")
                st.success(f"Ideal Answer Keywords: {q['answer']}")

            st.caption(f"Explanation: {q['explanation']}")
            st.divider()

        if "options" in quiz[0]:
            st.balloons()
            st.metric("Final Score", f"{score} / {len(quiz)}")