
import pyttsx3
import sys

print("Initializing pyttsx3...")
try:
    engine = pyttsx3.init()
    print("Speaking...")
    engine.say("音声再生のテストです。聞こえますか？")
    engine.runAndWait()
    print("Done.")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
