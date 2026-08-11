"""
Bypass extraction test for Page 54 and 79 (clean stdout coding).
"""
import sys, os
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv; load_dotenv('.env', override=True)
from google import genai
from google.genai import types as genai_types
import fitz

client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
doc = fitz.open("inputs/[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org.pdf")

# Test page 54 with multiple models and prompt formatting variations
page_54 = doc[53]
pix_54 = page_54.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
img_54 = pix_54.tobytes("jpeg")

models = ["models/gemini-3.5-flash-lite", "models/gemini-3.5-flash", "models/gemini-1.5-flash"]
prompts = [
    "Summarize the main history facts and details from this page image. Do not quote verbatim.",
    "Describe the visual text contents of this page in detail.",
]

print("--- TESTING PAGE 54 RECITATION BYPASS ---")
for model in models:
    for prompt in prompts:
        try:
            r = client.models.generate_content(
                model=model,
                contents=[
                    genai_types.Part.from_bytes(data=img_54, mime_type="image/jpeg"),
                    prompt
                ]
            )
            if r.text:
                print(f"SUCCESS: Model={model} | Prompt={prompt[:30]}...")
                print(f"Text Preview: {r.text[:200].strip()}\n")
                break
            else:
                reason = r.candidates[0].finish_reason if r.candidates else 'None'
                print(f"BLOCKED: Model={model} | Prompt={prompt[:30]}... | Finish Reason: {reason}")
        except Exception as e:
            print(f"ERROR  : Model={model} | Error={str(e)[:60]}")

# Test page 79
page_79 = doc[78]
pix_79 = page_79.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
img_79 = pix_79.tobytes("jpeg")
print("\n--- TESTING PAGE 79 SAFETY BYPASS ---")
try:
    r_79 = client.models.generate_content(
        model="models/gemini-3.5-flash-lite",
        contents=[
            genai_types.Part.from_bytes(data=img_79, mime_type="image/jpeg"),
            "Extract all text from this page verbatim."
        ],
        config=genai_types.GenerateContentConfig(
            safety_settings=[
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
                genai_types.SafetySetting(category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=genai_types.HarmBlockThreshold.BLOCK_NONE),
            ]
        )
    )
    if r_79.text:
        print("SUCCESS: Model=gemini-3.5-flash-lite on page 79")
        print(f"Text Preview: {r_79.text[:200].strip()}\n")
    else:
        reason = r_79.candidates[0].finish_reason if r_79.candidates else 'None'
        print(f"BLOCKED: Model=gemini-3.5-flash-lite | Finish Reason: {reason}")
except Exception as e:
    print("ERROR  : page 79:", e)

doc.close()
