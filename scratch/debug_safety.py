"""
Debugging safety filter response for Page 54 and 79.
"""
import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('.env', override=True)
from google import genai
from google.genai import types as genai_types
import fitz

client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
doc = fitz.open("inputs/[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org.pdf")

for page_num in [54, 79]:
    page = doc[page_num - 1]
    mat = fitz.Matrix(150/72, 150/72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img_bytes = pix.tobytes("jpeg")

    print(f"\n--- Testing Page {page_num} ---")
    try:
        response = client.models.generate_content(
            model="models/gemini-3.5-flash-lite",
            contents=[
                genai_types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                "Extract all text from this page. If safety filters are triggered, please report why."
            ],
            config=genai_types.GenerateContentConfig(
                # Set permissive safety settings to bypass false positive blocks on history textbooks
                safety_settings=[
                    genai_types.SafetySetting(
                        category=genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    genai_types.SafetySetting(
                        category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    genai_types.SafetySetting(
                        category=genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    genai_types.SafetySetting(
                        category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                ]
            )
        )
        print("Response Text:", response.text)
        print("Candidates safety ratings:", getattr(response.candidates[0], 'safety_ratings', None) if response.candidates else None)
    except Exception as e:
        print("Error details:", e)

doc.close()
