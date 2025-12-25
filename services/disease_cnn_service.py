import requests

HF_CNN_API = "https://YOUR-HF-SPACE.hf.space/predict"

def predict_disease_api(image_file):
    response = requests.post(
        HF_CNN_API,
        files={"file": image_file}
    )
    response.raise_for_status()
    return response.json()
