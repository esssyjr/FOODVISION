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

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Nigerian Food Vision API")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Keys
API_KEYS = [
    os.getenv("GOOGLE_API_KEY_1", "AIzaSyBvtwP2ulNHPQexfPhhR13U30pvF2OswrU"),
    os.getenv("GOOGLE_API_KEY_2", "AIzaSyD0dLXPPrZmLbnHOj3f9twHmT_PZc15wMo"),
]

# Store current food name for follow-up queries
food_history = {"last_detected_food": None}

# BaseModel for follow-up requests
class InfoRequest(BaseModel):
    food_name: str
    info_type: str  # One of the 8 options
    lang: str = "english"

# Image Upload + Detection Endpoint
@app.post("/detect")
async def detect_food(image: UploadFile = File(...), lang: str = Form(default="english")):
    try:
        image_data = await image.read()
        try:
            pil_image = Image.open(io.BytesIO(image_data))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image format. Upload a JPEG or PNG.")

        if pil_image.format not in ["JPEG", "PNG"]:
            raise HTTPException(status_code=400, detail="Only JPEG or PNG images are supported.")

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            pil_image.save(temp_file.name, format="JPEG")
            image_path = temp_file.name

        api_key = random.choice(API_KEYS)
        if not api_key:
            raise HTTPException(status_code=500, detail="No valid Google API key available.")

        generativeai.configure(api_key=api_key)

        # Upload image and detect
        uploaded = generativeai.upload_file(path=image_path, mime_type="image/jpeg")
        model = generativeai.GenerativeModel("gemini-1.5-flash")

        prompt = (
            f"This is an image of Nigerian food. Just return the name of the food item in one or two words. "
            f"Don't describe, explain, or add extra text. Output in {lang}."
        )

        response = model.generate_content([uploaded, prompt])
        food_name = response.text.strip()

        # Save last food name
        food_history["last_detected_food"] = food_name

        os.unlink(image_path)
        return {"food_name": food_name, "message": f"Detected food: {food_name}"}

    except Exception as e:
        logger.error(f"Error in /detect: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


# Follow-up Info Endpoint
@app.post("/food-info")
async def get_food_info(req: InfoRequest):
    try:
        if not req.food_name:
            req.food_name = food_history.get("last_detected_food")

        if not req.food_name:
            raise HTTPException(status_code=400, detail="No food name provided or previously detected.")

        api_key = random.choice(API_KEYS)
        generativeai.configure(api_key=api_key)
        model = generativeai.GenerativeModel("gemini-1.5-flash")

        prompt = (
            f"Give {req.info_type.lower()} information for {req.food_name}, a Nigerian food. "
            f"Respond in a short, friendly, and clear paragraph in {req.lang}."
        )

        response = model.generate_content(prompt)
        return {
            "food_name": req.food_name,
            "info_type": req.info_type,
            "response": response.text.strip()
        }

    except Exception as e:
        logger.error(f"Error in /food-info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


# Welcome
@app.get("/")
async def root():
    return {
        "message": "Welcome to the Nigerian Food Vision API! Upload a food image via POST /detect, then use /food-info with 8 options for further info."
    }
