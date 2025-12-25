import pandas as pd
import pickle
from sklearn.linear_model import LinearRegression

# Load dataset
data = pd.read_csv("data/simple_yield.csv")

X = data[["rainfall", "fertilizer", "temperature", "area"]]
y = data["yield"]

# Train model
model = LinearRegression()
model.fit(X, y)

# Save model
pickle.dump(model, open("models/yield_model.pkl", "wb"))

print("✅ Simple Yield Model trained successfully")
