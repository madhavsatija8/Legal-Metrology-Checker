"""
Preprocessing step of the OCR & extraction pipeline.

Real label photos are rarely clean: tilted camera angle, glare off
plastic/foil wrap, uneven lighting. This module fixes what it
reasonably can before OCR ever sees the image, since OCR accuracy on
a raw phone photo is often poor.
"""
import cv2
import numpy as np


def _deskew(gray: np.ndarray) -> np.ndarray:
    """
    Estimates and corrects rotation using the minimum-area bounding box
    of thresholded foreground pixels. Works well for a single dominant
    text block; a curved/wrapped label may need a more advanced method
    later (e.g. text-line-based skew estimation).
    """
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 10:
        return gray  # not enough foreground pixels to estimate skew reliably

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # Skip correction for near-zero angles — rotating a near-straight
    # image can introduce more distortion than it removes.
    if abs(angle) < 0.5:
        return gray

    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _enhance_contrast(gray: np.ndarray) -> np.ndarray:
    """CLAHE (adaptive histogram equalization) — helps with glare and uneven lighting."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _denoise(gray: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoising(gray, h=10)


def preprocess_image(image_path: str) -> np.ndarray:
    """
    Loads an image from disk and returns a cleaned, deskewed,
    contrast-enhanced grayscale array ready for OCR.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = _enhance_contrast(gray)
    gray = _denoise(gray)
    gray = _deskew(gray)
    return gray
