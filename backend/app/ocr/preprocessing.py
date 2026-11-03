"""
Preprocessing step of the OCR & extraction pipeline.

Real label photos are rarely clean: tilted camera angle, glare off
plastic/foil wrap, uneven lighting, and — very commonly on Indian retail
packaging — small, dense declaration text (net qty/MRP/mfg date block)
photographed on a curved or reflective surface with a phone camera. This
module fixes what it reasonably can before OCR ever sees the image,
since OCR accuracy on a raw phone photo is often poor.
"""
import cv2
import numpy as np

# Tesseract is most reliable when the text x-height is roughly 20-35px.
# Phone photos of the small mandatory-declaration block on Indian labels
# (Rule 7 allows numerals as small as 1mm) are frequently captured at a
# resolution well below that, so we upscale before anything else touches
# the image rather than only after OCR comes back empty-handed.
_TARGET_MIN_DIMENSION_PX = 1600


def _upscale_if_small(gray: np.ndarray) -> np.ndarray:
    h, w = gray.shape[:2]
    smaller_side = min(h, w)
    if smaller_side >= _TARGET_MIN_DIMENSION_PX:
        return gray
    scale = _TARGET_MIN_DIMENSION_PX / smaller_side
    # Cap the scale factor so a tiny thumbnail doesn't get blown up into a
    # blurry mess that just amplifies noise instead of adding detail.
    scale = min(scale, 3.0)
    return cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def _deskew(gray: np.ndarray) -> np.ndarray:
    """
    Estimates and corrects rotation using text pixel orientation.
    Only corrects small angles (0.5 to 15 degrees) to avoid rotating
    upright images into 90/180 degree sideways orientations.
    """
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    ys, xs = np.where(thresh > 0)
    coords = np.column_stack((xs, ys))
    if coords.shape[0] < 10:
        return gray

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    elif angle > 45:
        angle = 90 - angle
    else:
        angle = -angle

    # Only deskew if tilt is between 0.5 and 15 degrees.
    # Larger angles indicate global frame orientation artifacts, not line skew.
    if abs(angle) < 0.5 or abs(angle) > 15.0:
        return gray

    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _enhance_contrast(gray: np.ndarray) -> np.ndarray:
    """CLAHE (adaptive histogram equalization) -- helps with glare and uneven lighting."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _denoise(gray: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoising(gray, h=10)


def _sharpen(gray: np.ndarray) -> np.ndarray:
    """
    Unsharp mask. Cheap way to claw back edge definition lost to
    denoising, which matters more than usual here because a lot of the
    text we care about (net qty/MRP numerals) is small to begin with.
    """
    blurred = cv2.GaussianBlur(gray, (0, 0), sigmaX=3)
    return cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)


def _adaptive_binarize(gray: np.ndarray) -> np.ndarray:
    """
    Local (Gaussian) adaptive thresholding.
    """
    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=15,
    )


def preprocess_image(image_path: str, binarize: bool = False) -> np.ndarray:
    """
    Loads an image from disk and returns a cleaned, upscaled, deskewed,
    contrast-enhanced array ready for OCR.

    `binarize=False` (default) preserves high-contrast grayscale, which
    Tesseract's LSTM engine handles best on packaging photos.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = _upscale_if_small(gray)
    gray = _enhance_contrast(gray)
    gray = _denoise(gray)
    gray = _sharpen(gray)
    gray = _deskew(gray)
    if binarize:
        gray = _adaptive_binarize(gray)
    return gray
