"""Caméra USB et détection de visage (OpenCV Haar) sur le PC Hôte.

Séparé de la logique pour que recognizer.py et auth_flow.py restent testables sans caméra.
"""

import cv2

_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def detect_face(frame_bgr) -> "cv2.typing.MatLike | None":
    """Retourne le plus grand visage détecté (niveaux de gris) ou None."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces = _cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return gray[y:y + h, x:x + w]


def capture_face(camera_index: int = 0, attempts: int = 20) -> "cv2.typing.MatLike | None":
    """Ouvre la caméra USB, cherche un visage sur quelques images, le renvoie ou None."""
    cam = cv2.VideoCapture(camera_index)
    try:
        for _ in range(attempts):
            ok, frame = cam.read()
            if not ok:
                continue
            face = detect_face(frame)
            if face is not None:
                return face
    finally:
        cam.release()
    return None
