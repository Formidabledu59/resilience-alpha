"""Reconnaissance faciale légère (OpenCV LBPH) + stockage des visages enrôlés.

LBPH = Local Binary Patterns Histograms : classifieur intégré à OpenCV, très léger
(pas de gros modèle), adapté à une démo. Travaille sur des images en niveaux de gris
déjà préparées (visage détecté, recadré, redimensionné) : voir faces.py pour la préparation.

La reconnaissance est confirmée si le visage prédit correspond à l'identifiant ET si la
distance LBPH est sous le seuil (plus la distance est basse, meilleure est la correspondance).
"""

import json
from pathlib import Path

import cv2
import numpy as np

FACE_SIZE = (200, 200)   # taille normalisée des visages pour LBPH


class Recognizer:
    def __init__(self, model_dir: str, threshold: float = 70.0):
        self.dir = Path(model_dir)
        self.threshold = threshold
        self.dir.mkdir(parents=True, exist_ok=True)
        self._labels: dict[int, str] = {}   # label LBPH -> identifiant
        self._model: cv2.face.LBPHFaceRecognizer | None = None
        self._load_labels()
        self._train()

    @property
    def _labels_file(self) -> Path:
        return self.dir / "labels.json"

    def _load_labels(self) -> None:
        if self._labels_file.exists():
            self._labels = {int(k): v for k, v in json.loads(self._labels_file.read_text()).items()}

    def _label_for(self, username: str) -> int:
        for label, name in self._labels.items():
            if name == username:
                return label
        label = max(self._labels, default=-1) + 1
        self._labels[label] = username
        self._labels_file.write_text(json.dumps(self._labels))
        return label

    def _samples_dir(self, username: str) -> Path:
        d = self.dir / "faces" / username
        d.mkdir(parents=True, exist_ok=True)
        return d

    def enroll(self, username: str, gray_faces: list[np.ndarray]) -> int:
        """Ajoute des images de visage (niveaux de gris) pour un identifiant et réentraîne."""
        self._label_for(username)
        folder = self._samples_dir(username)
        start = len(list(folder.glob("*.png")))
        for i, face in enumerate(gray_faces):
            cv2.imwrite(str(folder / f"{start + i:03d}.png"), _prepare(face))
        self._train()
        return len(list(folder.glob("*.png")))

    def revoke(self, username: str) -> None:
        """Retire une habilitation : supprime ses images et son label, puis réentraîne."""
        folder = self.dir / "faces" / username
        if folder.exists():
            for f in folder.glob("*.png"):
                f.unlink()
            folder.rmdir()
        self._labels = {k: v for k, v in self._labels.items() if v != username}
        self._labels_file.write_text(json.dumps(self._labels))
        self._train()

    def _train(self) -> None:
        images, labels = [], []
        for label, username in self._labels.items():
            for png in (self.dir / "faces" / username).glob("*.png"):
                images.append(cv2.imread(str(png), cv2.IMREAD_GRAYSCALE))
                labels.append(label)
        if images:
            self._model = cv2.face.LBPHFaceRecognizer_create()
            self._model.train(images, np.array(labels))
        else:
            self._model = None

    def recognize(self, username: str, gray_face: np.ndarray) -> bool:
        """Vrai si le visage correspond à l'identifiant sous le seuil de distance."""
        if self._model is None or username not in self._labels.values():
            return False
        label, distance = self._model.predict(_prepare(gray_face))
        return self._labels.get(label) == username and distance <= self.threshold

    def enrolled_users(self) -> list[str]:
        return sorted(set(self._labels.values()))


def _prepare(gray: np.ndarray) -> np.ndarray:
    """Niveaux de gris, taille fixe, égalisation d'histogramme (robustesse à la lumière)."""
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, FACE_SIZE)
    return cv2.equalizeHist(gray.astype(np.uint8))
