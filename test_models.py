import spacy
import time

print("--- 🧪 Attempting to load spaCy model... ---")
start_time = time.time()

# This will load only the spaCy model
nlp = spacy.load("en_core_web_sm")

end_time = time.time()
print(f"--- ✅ spaCy loaded successfully in {end_time - start_time:.2f} seconds! ---")