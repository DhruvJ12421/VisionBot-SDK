import cv2
import numpy as np
from typing import Optional, Tuple, Union, List

class TemplateMatcher:
    """
    Handles robust OpenCV template matching on screen frames.
    Allows searching for visual elements with high accuracy and confidence thresholds.
    """

    def __init__(self, template_path: str):
        self.template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if self.template is None:
            raise FileNotFoundError(f"❌ Template image not found at: {template_path}")
        self.h, self.w = self.template.shape[:2]

    def match(
        self, 
        frame: np.ndarray, 
        threshold: float = 0.85, 
        search_region: Optional[Tuple[Union[int, float], Union[int, float], Union[int, float], Union[int, float]]] = None
    ) -> Optional[Tuple[int, int]]:
        """
        Searches for the template in the frame.
        Returns the center (x, y) coordinates of the match if confidence >= threshold, otherwise None.
        """
        h, w = frame.shape[:2]
        
        if search_region:
            x1, y1, x2, y2 = search_region
            ax1 = int(x1 * w) if isinstance(x1, float) else x1
            ay1 = int(y1 * h) if isinstance(y1, float) else y1
            ax2 = int(x2 * w) if isinstance(x2, float) else x2
            ay2 = int(y2 * h) if isinstance(y2, float) else y2
            
            ax1, ax2 = max(0, min(w, ax1)), max(0, min(w, ax2))
            ay1, ay2 = max(0, min(h, ay1)), max(0, min(h, ay2))
            
            crop_frame = frame[ay1:ay2, ax1:ax2]
        else:
            crop_frame = frame
            ax1, ay1 = 0, 0

        if crop_frame.shape[0] < self.h or crop_frame.shape[1] < self.w:
            return None

        res = cv2.matchTemplate(crop_frame, self.template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            match_x = ax1 + max_loc[0] + self.w // 2
            match_y = ay1 + max_loc[1] + self.h // 2
            return match_x, match_y

        return None


def get_color_ratio(
    frame: np.ndarray,
    lower_hsv: Tuple[int, int, int],
    upper_hsv: Tuple[int, int, int],
    region: Optional[Tuple[Union[int, float], Union[int, float], Union[int, float], Union[int, float]]] = None,
    apply_morphology: bool = True
) -> float:
    """Calculates the ratio of pixels (0.0 to 1.0) in a frame matching the HSV range."""
    h, w = frame.shape[:2]

    if region:
        x1, y1, x2, y2 = region
        ax1 = int(x1 * w) if isinstance(x1, float) else x1
        ay1 = int(y1 * h) if isinstance(y1, float) else y1
        ax2 = int(x2 * w) if isinstance(x2, float) else x2
        ay2 = int(y2 * h) if isinstance(y2, float) else y2
        
        ax1, ax2 = max(0, min(w, ax1)), max(0, min(w, ax2))
        ay1, ay2 = max(0, min(h, ay1)), max(0, min(h, ay2))
        
        crop = frame[ay1:ay2, ax1:ax2]
    else:
        crop = frame

    if crop.size == 0:
        return 0.0

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_hsv, upper_hsv)

    if apply_morphology:
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel)

    return np.sum(mask > 0) / mask.size


def get_multi_color_ratio(
    frame: np.ndarray,
    ranges: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]],
    region: Optional[Tuple[Union[int, float], Union[int, float], Union[int, float], Union[int, float]]] = None,
    apply_morphology: bool = True
) -> float:
    """Calculates the combined ratio of pixels matching multiple HSV ranges."""
    h, w = frame.shape[:2]

    if region:
        x1, y1, x2, y2 = region
        ax1 = int(x1 * w) if isinstance(x1, float) else x1
        ay1 = int(y1 * h) if isinstance(y1, float) else y1
        ax2 = int(x2 * w) if isinstance(x2, float) else x2
        ay2 = int(y2 * h) if isinstance(y2, float) else y2
        
        ax1, ax2 = max(0, min(w, ax1)), max(0, min(w, ax2))
        ay1, ay2 = max(0, min(h, ay1)), max(0, min(h, ay2))
        
        crop = frame[ay1:ay2, ax1:ax2]
    else:
        crop = frame

    if crop.size == 0:
        return 0.0

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)

    for lower, upper in ranges:
        mask = cv2.inRange(hsv, lower, upper)
        combined_mask = cv2.bitwise_or(combined_mask, mask)

    if apply_morphology:
        kernel = np.ones((3, 3), np.uint8)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_DILATE, kernel)

    return np.sum(combined_mask > 0) / combined_mask.size
