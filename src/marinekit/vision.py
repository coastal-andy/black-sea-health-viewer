"""Image / video tooling for ROV & AUV imagery.

Three building blocks:
  * frames:      iter_video_frames(), list_images(), enhance_underwater()
  * detection:   Detector: YOLO (closed-set, swap in litter weights) or YOLO-World (open-vocabulary,
                 type the classes you want, e.g. "plastic bag", "fishing net"; no training needed)
  * embeddings:  Embedder: CLIP / BioCLIP; zero-shot habitat/species labels from text prompts,
                 or few-shot (fit on a handful of labelled images) via logistic regression / k-NN

Heavy imports (torch, ultralytics, open_clip) happen lazily inside the classes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Sequence

import numpy as np
import pandas as pd
from PIL import Image

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
IMG_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

# Open-vocabulary prompts for marine litter (YOLO-World / CLIP)
LITTER_CLASSES = [
    "plastic bottle", "plastic bag", "fishing net", "rope", "tire", "metal can",
    "glass bottle", "plastic container", "cloth", "fishing line", "plastic debris",
]

# Black Sea benthic habitat prompts for zero-shot classification. Key = label, value = text prompt(s).
HABITAT_CLASSES: dict[str, list[str]] = {
    "sand": ["an underwater photo of a sandy seabed", "rippled sand on the sea floor"],
    "mud": ["an underwater photo of a muddy seabed", "soft fine mud sediment on the sea floor"],
    "rock": ["an underwater photo of rocky reef", "rocks and boulders on the sea floor"],
    "mussel_bed": ["an underwater photo of a dense mussel bed", "black mussels covering the seabed"],
    "shell_debris": ["an underwater photo of broken shells on the seabed", "shell hash sediment"],
    "seagrass": ["an underwater photo of a seagrass meadow", "long thin green blades of zostera seagrass on sandy bottom"],
    "phyllophora": ["an underwater photo of a dense field of red algae Phyllophora", "dark red leafy seaweed carpet on the seabed"],
    "brown_algae": ["an underwater photo of a Cystoseira brown algae forest on rocks", "bushy brown seaweed on shallow rocky reef"],
    "algae": ["an underwater photo of green filamentous algae covering rocks", "thin green algal turf on the sea floor"],
    "litter": ["an underwater photo of plastic litter on the seabed", "marine debris on the sea floor"],
    "water_column": ["an underwater photo of open turbid water with no seabed visible"],
}

# Species prompts (BioCLIP works best with scientific names)
SPECIES_CLASSES: dict[str, list[str]] = {
    "Mytilus galloprovincialis": ["a photo of Mytilus galloprovincialis, Mediterranean mussel"],
    "Rapana venosa": ["a photo of Rapana venosa, veined rapa whelk"],
    "Mnemiopsis leidyi": ["a photo of Mnemiopsis leidyi, comb jelly"],
    "Aurelia aurita": ["a photo of Aurelia aurita, moon jellyfish"],
    "Rhizostoma pulmo": ["a photo of Rhizostoma pulmo, barrel jellyfish"],
    "Phyllophora": ["a photo of Phyllophora red algae"],
    "Zostera": ["a photo of Zostera seagrass, eelgrass meadow"],
    "Gongolaria barbata": ["a photo of Gongolaria barbata (Cystoseira barbata), brown algae"],
    "fish": ["a photo of a fish underwater"],
}


# ---------------------------------------------------------------- frames ---

def device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def list_images(folder: str | Path) -> list[Path]:
    return sorted(p for p in Path(folder).rglob("*") if p.suffix.lower() in IMG_EXT)


def load_image(x) -> Image.Image:
    if isinstance(x, Image.Image):
        return x.convert("RGB")
    if isinstance(x, np.ndarray):
        return Image.fromarray(x).convert("RGB")
    return Image.open(x).convert("RGB")


def video_info(path: str | Path) -> dict:
    import cv2

    cap = cv2.VideoCapture(str(path))
    info = {"fps": cap.get(cv2.CAP_PROP_FPS) or 25.0, "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
    info["duration_s"] = info["frames"] / info["fps"] if info["fps"] else None
    cap.release()
    return info


def iter_video_frames(path: str | Path, every_s: float = 1.0, max_frames: int | None = None) -> Iterator[tuple[int, float, np.ndarray]]:
    """Yield (frame_index, t_seconds, RGB array) every `every_s` seconds."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(round(fps * every_s)))
    i = n = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                yield i, i / fps, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                n += 1
                if max_frames and n >= max_frames:
                    break
        i += 1
    cap.release()


def enhance_underwater(img, clip_limit: float = 2.0) -> np.ndarray:
    """Gray-world white balance + CLAHE on luminance. Helps a lot on green, murky Black Sea footage."""
    import cv2

    a = np.asarray(load_image(img)).astype(np.float32)
    means = a.reshape(-1, 3).mean(0)
    a = np.clip(a * (means.mean() / np.maximum(means, 1e-6)), 0, 255).astype(np.uint8)
    lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8)).apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


# ------------------------------------------------------------- detection ---

class Detector:
    """Thin wrapper over Ultralytics YOLO / YOLO-World.

    Detector("yolo11n.pt")                                   # COCO classes (bottle, cup, ...)
    Detector("path/to/litter_best.pt")                       # a litter model we fine-tune or download
    Detector("yolov8s-worldv2.pt", classes=LITTER_CLASSES)   # open-vocabulary, zero training
    """

    def __init__(self, weights: str = "yolo11n.pt", classes: Sequence[str] | None = None):
        from ultralytics import YOLO

        local = MODELS_DIR / weights
        if not Path(weights).exists() and (local.exists() or "/" not in weights):
            MODELS_DIR.mkdir(exist_ok=True)
            weights = str(local)  # keep downloaded weights in <project>/models
        self.weights = weights
        self.model = YOLO(weights)
        if classes:
            self.model.set_classes(list(classes))  # YOLO-World only
        self.names = self.model.names

    def detect(self, images: Sequence, conf: float = 0.25, ids: Sequence | None = None, imgsz: int = 640) -> pd.DataFrame:
        """Run on a list of images (paths / PIL / arrays). Returns one row per box."""
        ids = list(ids) if ids is not None else list(range(len(images)))
        rows = []
        for img_id, img in zip(ids, images):
            arr = np.asarray(load_image(img))
            res = self.model.predict(arr, conf=conf, imgsz=imgsz, verbose=False, device=device())[0]
            for b in res.boxes:
                x1, y1, x2, y2 = b.xyxy[0].tolist()
                c = int(b.cls)
                rows.append(dict(image_id=img_id, cls=c, label=self.names[c], conf=round(float(b.conf), 3),
                                 x1=x1, y1=y1, x2=x2, y2=y2, area_px=(x2 - x1) * (y2 - y1)))
        return pd.DataFrame(rows, columns=["image_id", "cls", "label", "conf", "x1", "y1", "x2", "y2", "area_px"])

    @staticmethod
    def annotate(img, boxes: pd.DataFrame) -> Image.Image:
        """Draw boxes from detect() onto an image."""
        from PIL import ImageDraw

        im = load_image(img).copy()
        d = ImageDraw.Draw(im)
        w = max(2, im.width // 300)
        for _, b in boxes.iterrows():
            d.rectangle([b.x1, b.y1, b.x2, b.y2], outline=(255, 64, 64), width=w)
            d.text((b.x1 + 3, max(0, b.y1 - 12)), f"{b.label} {b.conf:.2f}", fill=(255, 255, 0))
        return im


# ------------------------------------------------------------ embeddings ---

MODELS = {
    "clip-b32": ("ViT-B-32", "laion2b_s34b_b79k"),   # small + fast, general
    "bioclip": ("hf-hub:imageomics/bioclip", None),  # trained on the Tree of Life: best for species
}


class Embedder:
    """CLIP-family image/text embeddings for zero-shot and few-shot classification."""

    def __init__(self, model: str = "clip-b32"):
        import open_clip
        import torch

        name, pretrained = MODELS.get(model, (model, None))
        self.dev = device()
        if pretrained:
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(name, pretrained=pretrained)
            self.tokenizer = open_clip.get_tokenizer(name)
        else:
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(name)
            self.tokenizer = open_clip.get_tokenizer(name)
        self.model = self.model.to(self.dev).eval()
        self.torch = torch
        self.clf = None

    def embed_images(self, images: Sequence, batch: int = 32) -> np.ndarray:
        out = []
        with self.torch.no_grad():
            for i in range(0, len(images), batch):
                x = self.torch.stack([self.preprocess(load_image(im)) for im in images[i:i + batch]]).to(self.dev)
                f = self.model.encode_image(x)
                out.append((f / f.norm(dim=-1, keepdim=True)).float().cpu().numpy())
        return np.concatenate(out) if out else np.zeros((0, 512), dtype=np.float32)

    def embed_text(self, texts: Sequence[str]) -> np.ndarray:
        with self.torch.no_grad():
            t = self.tokenizer(list(texts)).to(self.dev)
            f = self.model.encode_text(t)
            return (f / f.norm(dim=-1, keepdim=True)).float().cpu().numpy()

    def zero_shot(self, images_or_embs, classes: dict[str, list[str]] = HABITAT_CLASSES, temperature: float = 100.0) -> pd.DataFrame:
        """Probability per class for each image. Prompts per class are averaged."""
        embs = images_or_embs if isinstance(images_or_embs, np.ndarray) else self.embed_images(images_or_embs)
        labels = list(classes)
        T = np.stack([self.embed_text(classes[k]).mean(0) for k in labels])
        T /= np.linalg.norm(T, axis=1, keepdims=True)
        logits = temperature * embs @ T.T
        p = np.exp(logits - logits.max(1, keepdims=True))
        p /= p.sum(1, keepdims=True)
        df = pd.DataFrame(p, columns=labels)
        df.insert(0, "pred", df[labels].idxmax(axis=1))
        df.insert(1, "conf", df[labels].max(axis=1).round(3))
        return df

    def fit_few_shot(self, embs: np.ndarray, labels: Sequence[str]):
        """Train a tiny classifier on a few labelled embeddings (5-20 per class is often enough)."""
        from sklearn.linear_model import LogisticRegression

        self.clf = LogisticRegression(max_iter=2000, C=10.0).fit(embs, labels)
        return self

    def predict_few_shot(self, embs: np.ndarray) -> pd.DataFrame:
        if self.clf is None:
            raise RuntimeError("call fit_few_shot first")
        p = self.clf.predict_proba(embs)
        df = pd.DataFrame(p, columns=self.clf.classes_)
        df.insert(0, "pred", self.clf.classes_[p.argmax(1)])
        df.insert(1, "conf", p.max(1).round(3))
        return df


def smooth_labels(pred: Sequence[str], window: int = 5) -> list[str]:
    """Majority filter along an AUV transect: removes single-frame flicker in habitat labels."""
    pred = list(pred)
    h = window // 2
    out = []
    for i in range(len(pred)):
        seg = pred[max(0, i - h): i + h + 1]
        out.append(max(set(seg), key=seg.count))
    return out
