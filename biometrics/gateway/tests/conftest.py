import numpy as np


def striped_face(orientation: str, seed: int) -> np.ndarray:
    """Visage synthétique texturé (rayures) pour tester le pipeline LBPH sans vraie photo."""
    rng = np.random.default_rng(seed)
    base = np.zeros((200, 200), np.uint8)
    if orientation == "vertical":
        base[:, ::4] = 255
    else:
        base[::4, :] = 255
    noise = rng.integers(0, 30, base.shape, dtype=np.uint8)
    return np.clip(base.astype(int) + noise, 0, 255).astype(np.uint8)
