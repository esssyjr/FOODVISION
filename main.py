from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import os
import tempfile
from google import generativeai
import random
import io
import logging
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App initialization
app = FastAPI(title="Nigerian Food Vision API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set API Keys
API_KEYS = [
    os.getenv("GOOGLE_API_KEY_1", "AIzaSyBvtwP2ulNHPQexfPhhR13U30pvF2OswrU"),
    os.getenv("GOOGLE_API_KEY_2", "AIzaSyD0dLXPPrZmLbnHOj3f9twHmT_PZc15wMo"),
]

# Model options
INFO_OPTIONS = [
    "Calories content",
    "Diabetic friendly?",
    "Preparation method",
    "Ingredients",
    "Nutritional content",
    "Allergen info",
    "Hypertension friendly?",
    "Kidney safe?"
]

# Configure Gemini
def configure_gemini():
    api_key = random.choice(API_KEYS)
    if not api_key:
        raise ValueError("No valid API key provided.")
    generativeai.configure(api_key=api_key)
    return generativeai.GenerativeModel("gemini-1.5-flash")

# Endpoint 1: Upload image and detect food name
@app.post("/detect_food")
async def detect_food(image: UploadFile = File(...), lang: str = Form(default="english")):
    try:
        image_data = await image.read()
        img = Image.open(io.BytesIO(image_data))

        if img.format not in ["JPEG", "PNG"]:
            raise HTTPException(status_code=400, detail="Only JPEG or PNG images are supported.")

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            img.save(temp_file.name)
            image_path = temp_file.name

        model = configure_gemini()
        uploaded = generativeai.upload_file(path=image_path, mime_type="image/jpeg")

        prompt = f"Identify the name of the Nigerian food shown in the image. Respond with ONLY the name (e.g., Jollof rice, Egusi soup, etc)."
        response = model.generate_content([uploaded, prompt])
        os.unlink(image_path)

        food_name = response.text.strip()

        return {
            "food_name": food_name,
            "options": INFO_OPTIONS
        }

    except Exception as e:
        logger.error(f"Error in detect_food: {e}")
        raise HTTPException(status_code=500, detail=f"Detection error: {e}")

# Request model for /food_info
class InfoRequest(BaseModel):
    food_name: str
    info_type: str  # e.g., "Calories content"

# Endpoint 2: Get more info about detected food
@app.post("/food_info")
async def food_info(request: InfoRequest):
    try:
        model = configure_gemini()

        prompt = (
            f"You are a Nigerian food expert. Give specific information about {request.food_name}. "
            f"The user is asking: '{request.info_type}'. Provide the answer in a friendly, short, and informative tone."
        )
        response = model.generate_content(prompt)

        return {
            "food_name": request.food_name,
            "info_type": request.info_type,
            "response": response.text.strip()
        }

    except Exception as e:
        logger.error(f"Error in food_info: {e}")
        raise HTTPException(status_code=500, detail=f"Info error: {e}")

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to Nigerian Food Vision API. Use /detect_food to upload a cuisine image and /food_info to query for more info."
    }
