import face_recognition
import json

train_imgs = [
    { "path": "images/obama.jpg", "name": "obama" },
    { "path": "images/biden.jpg", "name": "biden" },
    { "path": "images/trump.jpg", "name": "trump" },
]


def learn_face(train_imgs) -> None:
    # データの解析
    face_data = []
    for data in train_imgs:
        img = face_recognition.load_image_file(data["path"])
        face_encodings = face_recognition.face_encodings(img)
        if len(face_encodings) > 0:
            face_data.append({
                "name": data["name"],
                "face_encodings": face_encodings[0].tolist()
            })
        else:
            print(f"No face found in {data['path']}")

    # 出力
    with open("face_encodings.json", "w") as f:
        json.dump(face_data, f, indent=4)
        print("successed save face encodings.")

if __name__ == "__main__":
    learn_face(train_imgs)

    
    
