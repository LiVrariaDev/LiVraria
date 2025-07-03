import face_recognition
import json

def face_rec(img_path: str) -> bool:
    # 読込
    face_data = []
    with open("face_encodings.json", "r") as f:
        face_data = json.load(f)

    # データ解析
    img = face_recognition.load_image_file(img_path)
    face_encodings = face_recognition.face_encodings(img)

    if len(face_encodings) > 0:
        face_encoding = face_encodings[0]
    else:
        print(f"No face found in {img_path}")
        return False

    # 顔認識(比較)
    for data in face_data:
        result = face_recognition.compare_faces([data["face_encodings"]], face_encoding)
        if result[0]:
            print(f"{img_path} is a match with {data['name']}!")
            return True
    
    print(f"{img_path} is not a match with any known faces.")
        
    
if __name__ == "__main__":
    img_path = "images/putin.jpg"
    face_rec(img_path)
