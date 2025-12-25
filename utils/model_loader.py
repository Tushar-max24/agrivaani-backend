import pickle
# import tensorflow as tf


# ---------------- Crop Model ----------------
def load_crop_model():
    with open("models/crop_model.pkl", "rb") as f:
        return pickle.load(f)


# ---------------- Fertilizer Model ----------------
def load_fertilizer_model():
    with open("models/fertilizer_model.pkl", "rb") as f:
        fertilizer_model = pickle.load(f)

    with open("models/crop_encoder.pkl", "rb") as f:
        crop_encoder = pickle.load(f)

    with open("models/soil_encoder.pkl", "rb") as f:
        soil_encoder = pickle.load(f)

    return fertilizer_model, crop_encoder, soil_encoder


# ---------------- Yield Model ----------------
def load_yield_model():
    with open("models/yield_model.pkl", "rb") as f:
        return pickle.load(f)


def load_disease_model():
    return None
    # return tf.keras.models.load_model("models/disease_model.h5")