from __future__ import annotations

from src.vision.roi import crop_person_rois, expand_box


def test_expand_box():
    # box = [x1, y1, x2, y2]
    # width=100, height=100, ratio=0.1
    # width of box = 40 (20 to 60)
    # pad_x = 40 * 0.1 = 4
    # pad_y = 40 * 0.1 = 4
    # result: x1=16, y1=16, x2=64, y2=64
    box = (20, 20, 60, 60)
    res = expand_box(box, width=100, height=100, ratio=0.1)
    assert res == (16, 16, 64, 64)

def test_expand_box_clamped():
    box = (5, 5, 95, 95)
    # box width=90, pad=9. x1=5-9=-4 -> 0. x2=95+9=104 -> 100
    res = expand_box(box, width=100, height=100, ratio=0.1)
    assert res == (0, 0, 100, 100)

class DummyFrame:
    def __init__(self, shape):
        self.shape = shape
        
    def __getitem__(self, idx):
        return f"crop_{idx}"

def test_crop_person_rois():
    frame = DummyFrame((100, 100, 3))
    
    # box1 is large enough (size > min_size)
    box1 = (20, 20, 60, 60)
    
    # box2 is too small (size < min_size=16) even after padding
    box2 = (10, 10, 15, 15)  # w=5, h=5
    
    rois = crop_person_rois(frame, [box1, box2], pad_ratio=0.1, min_size=16)
    
    assert len(rois) == 1
    roi_box, crop = rois[0]
    
    assert roi_box == (16, 16, 64, 64)
    # crop should be the result of frame[16:64, 16:64]
    assert crop == "crop_(slice(16, 64, None), slice(16, 64, None))"

def test_crop_person_rois_min_size():
    frame = DummyFrame((100, 100, 3))
    
    box = (10, 10, 20, 20)  # size = 10, after pad (ratio=0) size=10
    
    # Should skip because 10 < 16
    rois = crop_person_rois(frame, [box], pad_ratio=0.0, min_size=16)
    assert len(rois) == 0
    
    # Should include because 10 >= 10
    rois = crop_person_rois(frame, [box], pad_ratio=0.0, min_size=10)
    assert len(rois) == 1
