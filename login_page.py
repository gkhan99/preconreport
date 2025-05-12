import streamlit as st
from openai import OpenAI
from docx import Document
from docx.shared import Cm
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
import base64
import tiktoken
import os

# === CONFIG ===
# Instantiate the new OpenAI client (v1.x+)
client = OpenAI(api_key=st.secrets["api"]["key"])

# === HELPERS ===

def encode_image(image_path: str) -> str:
    """Read an image file and return a base64 data URI."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

def build_prompt() -> str:
    """The system/user prompt for classifying structural damage."""
    return (
        "As a civil engineer, I have some photos and would like to classify them into different categories before starting a project. "
        "Find if it contains any visible cracks, peeling paint, possible water damage, visual discoloration, honeycombing, spalling or any other possible damage. "
        "If nothing, then just mention a statement about the image. Sound it technical and to the point."
    )

def estimate_cost(prompt_text: str, response_text: str, model: str="gpt-4o") -> float:
    """Estimate API cost with tiktoken (input @ $0.005/1K, output @ $0.015/1K)."""
    enc = tiktoken.encoding_for_model(model)
    in_tokens  = len(enc.encode(prompt_text))
    out_tokens = len(enc.encode(response_text))
    return round(in_tokens * 0.005/1000 + out_tokens * 0.015/1000, 6)

def generate_report(image_paths: list[str], output_path: str="output_report.docx") -> tuple[float,str]:
    """
    For each image:
      1. Encode to base64 URI
      2. Send a single message with [{type:"text",…}, {type:"image_url",…}]
      3. Extract and format the comment
      4. Build a .docx with image + comment
    Returns total_cost and the .docx path.
    """
    doc = Document()
    total_cost = 0.0

    for idx, img_path in enumerate(image_paths, start=1):
        data_uri = encode_image(img_path)
        try:
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text",      "text": build_prompt()},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    }
                ],
                max_tokens=200,
            )
            comment = resp.choices[0].message.content.strip().capitalize()
            if not comment.endswith("."):
                comment += "."
            total_cost += estimate_cost(build_prompt(), comment)

        except Exception as e:
            comment = f"⚠️ Error analyzing image: {e}"

        # Number
        p_num = doc.add_paragraph(f"Image No.: {idx}")
        p_num.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        # Image
        p_img = doc.add_paragraph()
        run   = p_img.add_run()
        run.add_picture(img_path, width=Cm(15), height=Cm(7.5))
        p_img.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        # Comment
        p_txt = doc.add_paragraph(f"Assessment: {comment}")
        p_txt.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        doc.add_paragraph("")  # spacer

    doc.save(output_path)
    return total_cost, output_path

# === STREAMLIT PAGES ===

def login_page():
    st.title("🔐 Hirani Pre-Con Report Login")
    user = st.text_input("Username")
    pwd  = st.text_input("Password", type="password")

    if st.button("Log in"):
        if (user == st.secrets["auth"]["username"]
         and pwd  == st.secrets["auth"]["password"]):
            st.session_state.logged_in = True
            st.success("Login successful! Please upload images.")
        else:
            st.error("Invalid username or password")

def image_analysis_page():
    st.title("🖼️ Image Analysis & Report Generation")

    uploaded = st.file_uploader(
        "Upload images (.jpg/.jpeg/.png)",
        accept_multiple_files=True
    )
    if not uploaded:
        st.info("Please upload one or more images.")
        return

    os.makedirs("temp_images", exist_ok=True)
    image_paths: list[str] = []
    for f in uploaded:
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png"):
            st.error(f"Invalid extension on `{f.name}` – only .jpg/.jpeg/.png allowed.")
            continue
        path = os.path.join("temp_images", f.name)
        with open(path, "wb") as out:
            out.write(f.getbuffer())
        image_paths.append(path)

    if not image_paths:
        st.warning("No valid images to process.")
        return

    st.write("✅ Saved images:", image_paths)
    if st.button("Generate Report"):
        cost, docx_file = generate_report(image_paths)
        st.success("Report generated!")
        st.write(f"• File: `{docx_file}`")
        st.write(f"• Estimated API cost: ${cost}")
        with open(docx_file, "rb") as docf:
            st.download_button("📥 Download .DOCX", docf, file_name=os.path.basename(docx_file))

# === ENTRY POINT ===

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if st.session_state.logged_in:
    image_analysis_page()
else:
    login_page()
