import face_recognition

train_img_names = ["images/obama.jpg", "images/biden.jpg", "images/trump.jpg"]

test_img_name = "images/obama-test.jpg"

# 学習データの読込
train_imgs = []
for name in train_img_names:
    img = face_recognition.load_image_file(name)
    train_imgs.append(img)

# テストデータの読込
test_img = face_recognition.load_image_file(test_img_name)

# 学習データの顔特徴量を取得
train_face_encodings = []
for img in train_imgs:
    face_encodings = face_recognition.face_encodings(img)
    if len(face_encodings) > 0:
        train_face_encodings.append(face_encodings[0])
    else:
        print(f"No face found in {name}")

# テストデータの顔特徴量を取得
test_face_encodings = face_recognition.face_encodings(test_img)
if len(test_face_encodings) > 0:
    test_face_encoding = test_face_encodings[0]
else:
    print(f"No face found in {test_img_name}")
    test_face_encoding = None

# 顔認識(比較)
results = []
for train_face_encoding in train_face_encodings:
    result = face_recognition.compare_faces([train_face_encoding], test_face_encoding)
    results.append(result[0])

print("Results:")
for name, result in zip(train_img_names, results):
    if result:
        print(f"{name} is a match!")
    else:
        print(f"{name} is not a match.")

