import os
import uuid

def save_file(file):
    os.makedirs("storage/images", exist_ok=True)

    filename = f"{uuid.uuid4()}.jpg"
    path = os.path.join("storage/images", filename)

    with open(path, "wb") as f:
        f.write(file.file.read())

    return path