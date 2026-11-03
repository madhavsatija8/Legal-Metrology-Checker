import os
import shutil
from dataclasses import dataclass

import numpy as np
import pytesseract

# Auto-locate tesseract executable on Windows if not present in PATH
if not shutil.which("tesseract"):
    _possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe"),
    ]
    for _p in _possible_paths:
        if os.path.exists(_p):
            pytesseract.pytesseract.tesseract_cmd = _p
            break


@dataclass
class TextBlock:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float
    block_num: int
    par_num: int
    line_num: int

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.left + self.width, self.top + self.height)

    @property
    def line_key(self) -> tuple[int, int, int]:
        """
        Tesseract's `line_num` resets to 1 at the start of every new
        block/paragraph, so grouping on line_num alone merges unrelated
        lines from different blocks together. The (block, par, line)
        triple is what's actually unique.
        """
        return (self.block_num, self.par_num, self.line_num)


def run_ocr(image: np.ndarray, lang: str = "eng+hin", config: str = "--oem 1 --psm 11") -> list[TextBlock]:
    """
    Returns one TextBlock per detected word with confidence > 0.
    Tesseract's confidence is -1 for non-text regions; those are dropped.
    """
    try:
        data = pytesseract.image_to_data(image, lang=lang, config=config, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractError:
        # Fall back to English-only if secondary language pack isn't installed
        if "+" in lang:
            data = pytesseract.image_to_data(
                image, lang="eng", config=config, output_type=pytesseract.Output.DICT
            )
        else:
            raise

    blocks: list[TextBlock] = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        blocks.append(
            TextBlock(
                text=text,
                left=data["left"][i],
                top=data["top"][i],
                width=data["width"][i],
                height=data["height"][i],
                confidence=conf,
                block_num=data["block_num"][i],
                par_num=data["par_num"][i],
                line_num=data["line_num"][i],
            )
        )
    return blocks


def group_into_lines(blocks: list[TextBlock]) -> list["Line"]:
    """
    Joins word-level blocks back into line-level groups using spatial Y-clustering
    and horizontal column-gap splitting to handle side-by-side declaration columns.
    """
    if not blocks:
        return []

    # Sort blocks vertically first
    words_sorted = sorted(blocks, key=lambda b: (b.top, b.left))
    line_clusters: list[list[TextBlock]] = []

    for w in words_sorted:
        placed = False
        for cluster in line_clusters:
            avg_y = sum(b.top for b in cluster) / len(cluster)
            avg_h = sum(b.height for b in cluster) / len(cluster)
            if abs(w.top - avg_y) < max(12.0, avg_h * 0.6):
                cluster.append(w)
                placed = True
                break
        if not placed:
            line_clusters.append([w])

    result: list[Line] = []
    for cluster in line_clusters:
        cluster.sort(key=lambda b: b.left)
        # Calculate horizontal gaps between consecutive words to split columns
        sub_lines: list[list[TextBlock]] = []
        curr: list[TextBlock] = [cluster[0]]

        for w in cluster[1:]:
            prev = curr[-1]
            gap = w.left - (prev.left + prev.width)
            avg_w = sum(b.width for b in curr) / len(curr)
            # Split line if gap exceeds 80px or 3x average word width
            gap_threshold = max(80.0, avg_w * 3.0)
            if gap > gap_threshold:
                sub_lines.append(curr)
                curr = [w]
            else:
                curr.append(w)
        sub_lines.append(curr)

        for sub in sub_lines:
            text = " ".join(w.text for w in sub)
            result.append(
                Line(
                    text=text,
                    top=min(w.top for w in sub),
                    bottom=max(w.top + w.height for w in sub),
                    left=min(w.left for w in sub),
                    right=max(w.left + w.width for w in sub),
                    avg_word_height_px=sum(w.height for w in sub) / len(sub),
                )
            )

    result.sort(key=lambda l: (l.top, l.left))
    return result


@dataclass
class Line:
    """A line of OCR'd text with its pixel bounding box, for font-size/readability checks (Step 5)."""

    text: str
    top: int
    bottom: int
    left: int
    right: int
    avg_word_height_px: float

    @property
    def height_px(self) -> int:
        return self.bottom - self.top
