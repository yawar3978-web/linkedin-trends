from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client()  # reads GEMINI_API_KEY from your .env file

reply = client.models.generate_content(
    model="gemini-3.6-flash",
    contents="Say hello to a data science student in one sentence.",
)
print(reply.text)