"""
Text detection & OCR step. Runs Tesseract in "data" mode so we get a
bounding box, confidence score, and pixel height per detected word —
the bounding box height is what the readability/font-size module will
eventually need, not just the raw string.
"""
from dataclasses import dataclass

import numpy as np
import pytesseract


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


def run_ocr(image: np.ndarray, lang: str = "eng") -> list[TextBlock]:
    """
    Returns one TextBlock per detected word with confidence > 0.
    Tesseract's confidence is -1 for non-text regions; those are dropped.
    Multiple Indian-language packs (e.g. 'eng+hin') can be passed via
    `lang` once the corresponding tesseract-ocr-<lang> package is
    installed, since many labels carry both English and a regional
    language.
    """
    data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

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
    Joins word-level blocks back into line-level groups, in reading order.
    Keeps each line's bounding box (not just its text) because the
    readability/font-size check (Step 5) needs the pixel height of the
    text that carries each declaration — that's lost forever if this
    function returns plain strings.
    """
    lines: dict[tuple[int, int, int], list[TextBlock]] = {}
    for b in blocks:
        lines.setdefault(b.line_key, []).append(b)

    # Order groups by vertical position (average top of their words), not
    # by line_num, since line_num is only unique within a single block.
    def _avg_top(group: list[TextBlock]) -> float:
        return sum(w.top for w in group) / len(group)

    ordered_groups = sorted(lines.values(), key=_avg_top)

    result: list[Line] = []
    for group in ordered_groups:
        words = sorted(group, key=lambda b: b.left)
        text = " ".join(w.text for w in words)
        result.append(
            Line(
                text=text,
                top=min(w.top for w in words),
                bottom=max(w.top + w.height for w in words),
                left=min(w.left for w in words),
                right=max(w.left + w.width for w in words),
                # Average rather than max word height: a line like "MRP: Rs.
                # 185.00" mixes a small colon glyph with taller digits, and
                # the *typical* character height is what the mm conversion
                # in Step 5 should compare against the rule's slab table,
                # not one outlier glyph.
                avg_word_height_px=sum(w.height for w in words) / len(words),
            )
        )
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
