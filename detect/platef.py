import cv2
import os
import traceback
import matplotlib.pyplot as plt
import numpy as np
import openvino.runtime as ov
from PIL import Image
import time
import json
import yaml
import easyocr

# --- Configuration for Car Plate Detection (Stage 1) ---
CAR_MODEL_XML = "model_platecar/model/saved_model.xml"
CAR_INPUT_HEIGHT = 640
CAR_INPUT_WIDTH = 640
CAR_MEAN_BGR = np.array([103.53, 116.28, 123.675], dtype=np.float32)
CAR_STD_BGR = np.array([57.375, 57.12, 58.395], dtype=np.float32)
CAR_CONFIDENCE_THRESHOLD = 0.53

# --- Configuration for Plate Reading (Stage 2) ---
PLATE_BASE_FOLDER = "plate_ex"
PLATE_MODEL_XML = os.path.join(PLATE_BASE_FOLDER, "model", "saved_model.xml")
PLATE_MODEL_BIN = os.path.join(PLATE_BASE_FOLDER, "model", "saved_model.bin")
PLATE_DM_JSON = os.path.join(PLATE_BASE_FOLDER, "model_meta", "dm.json")
PLATE_TRANSFORMS_YAML = os.path.join(PLATE_BASE_FOLDER, "model_meta", "transforms.yaml")
PLATE_CONFIDENCE_THRESHOLD = 0.54

# --- OCR Configuration ---
OCR_LANGUAGES = ['en']
OCR_ALLOWLIST_NUMBERS = '0123456789'
OCR_GPU = False

# --- File paths ---
INPUT_CAR_IMAGE = "OIP.jpg"  # Input car image
TEMP_PLATE_IMAGE = "plate_crop_stage1.jpg"  # Intermediate plate image
OUTPUT_FINAL_IMAGE = "output_detection_ocr.jpg"  # Final output with OCR results

# --- Stage 1 Helper Functions ---
def preprocess_image_car(image, target_height, target_width, mean, std):
    """Preprocess image for car plate detection."""
    original_height, original_width = image.shape[:2]
    print(f"Original image dimensions (HxW): ({original_height}, {original_width})")
    scale_h = target_height / original_height
    scale_w = target_width / original_width
    scale = min(scale_h, scale_w)
    new_height = int(original_height * scale)
    new_width = int(original_width * scale)
    resized_image = cv2.resize(image, (new_width, new_height))
    
    padded_image = np.zeros((target_height, target_width, 3), dtype=np.uint8)
    padded_image[0:new_height, 0:new_width] = resized_image
    pad_y = 0
    pad_x = 0
    
    blob = padded_image.astype(np.float32)
    blob -= mean
    blob /= std
    blob = blob.transpose(2, 0, 1)  # CHW
    blob = np.expand_dims(blob, axis=0)  # NCHW
    return blob, (original_height, original_width), scale, pad_x, pad_y

def detect_and_correct_rotation(plate_img):
    """Detect and correct plate rotation if needed."""
    ANGLE_THRESHOLD = 2.0
    
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return plate_img
    
    c = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(c)
    angle = rect[2]
    
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90
    
    if abs(angle) < ANGLE_THRESHOLD:
        return plate_img
    
    h, w = plate_img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(plate_img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    
    return rotated

# --- Stage 2 Helper Functions ---
def load_metadata():
    """Load class mapping and preprocessing info for plate reading."""
    try:
        with open(PLATE_DM_JSON, 'r') as f:
            dm_data = json.load(f)
        class_map = {int(k): v['name'] for k, v in dm_data.items()}
    except Exception as e:
        print(f"Error loading dm.json: {e}")
        return None, None

    try:
        with open(PLATE_TRANSFORMS_YAML, 'r') as f:
            transforms_data = yaml.safe_load(f)
        preprocess_params = {}
        transform_list = transforms_data.get('valid', []) or transforms_data.get('train', [])
        
        for transform in transform_list:
            if 'RescaleWithPadding' in transform:
                preprocess_params['target_height'] = transform['RescaleWithPadding']['height']
                preprocess_params['target_width'] = transform['RescaleWithPadding']['width']
                break
        for transform in transform_list:
            if 'NormalizeMeanStd' in transform:
                preprocess_params['mean'] = np.array(transform['NormalizeMeanStd']['mean'], dtype=np.float32)
                preprocess_params['std'] = np.array(transform['NormalizeMeanStd']['std'], dtype=np.float32)
                break

        if 'target_height' not in preprocess_params:
            preprocess_params['target_height'] = 640
            preprocess_params['target_width'] = 640
        if 'mean' not in preprocess_params:
            preprocess_params['mean'] = np.array([0,0,0], dtype=np.float32)
            preprocess_params['std'] = np.array([1,1,1], dtype=np.float32)

    except Exception as e:
        print(f"Error loading transforms.yaml: {e}")
        return None, None

    return class_map, preprocess_params

def preprocess_image_plate(image_path, target_h, target_w, mean, std):
    """Preprocess image for plate reading."""
    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return None, None, None, None

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        print(f"Error: Could not read image at {image_path}")
        return None, None, None, None

    original_h, original_w = img_bgr.shape[:2]
    scale = min(target_h / original_h, target_w / original_w)
    new_h, new_w = int(original_h * scale), int(original_w * scale)
    resized_img = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    pad_h = target_h - new_h
    pad_w = target_w - new_w
    top_pad = pad_h // 2
    bottom_pad = pad_h - top_pad
    left_pad = pad_w // 2
    right_pad = pad_w - left_pad

    padded_img = cv2.copyMakeBorder(resized_img, top_pad, bottom_pad,
                                   left_pad, right_pad,
                                   cv2.BORDER_CONSTANT, value=(114, 114, 114))

    img_float = padded_img.astype(np.float32)
    img_normalized = (img_float - mean) / std
    img_chw = img_normalized.transpose((2, 0, 1))
    input_tensor = np.expand_dims(img_chw, axis=0)

    scaling_meta = {
        'original_h': original_h,
        'original_w': original_w,
        'scale': scale,
        'top_pad': top_pad,
        'left_pad': left_pad
    }
    return input_tensor, img_bgr, scaling_meta, padded_img

def scale_coords(coords, scaling_meta, target_h, target_w):
    """Scale coordinates back to original image."""
    x_min, y_min, x_max, y_max = coords
    x_min_unpad = x_min - scaling_meta['left_pad']
    y_min_unpad = y_min - scaling_meta['top_pad']
    x_max_unpad = x_max - scaling_meta['left_pad']
    y_max_unpad = y_max - scaling_meta['top_pad']

    scale = scaling_meta['scale']
    if scale == 0:
        return 0, 0, 0, 0

    orig_x_min = x_min_unpad / scale
    orig_y_min = y_min_unpad / scale
    orig_y_max = y_max_unpad / scale
    orig_x_max = x_max_unpad / scale

    orig_h, orig_w = scaling_meta['original_h'], scaling_meta['original_w']
    orig_x_min = max(0, min(orig_x_min, orig_w))
    orig_y_min = max(0, min(orig_y_min, orig_h))
    orig_x_max = max(0, min(orig_x_max, orig_w))
    orig_y_max = max(0, min(orig_y_max, orig_h))

    return int(orig_x_min), int(orig_y_min), int(orig_x_max), int(orig_y_max)

def main():
    print("=== Starting License Plate Detection and Reading Pipeline ===")
    
    # --- Stage 1: Detect License Plate from Car Image ---
    print("\n=== Stage 1: License Plate Detection ===")
    
    if not os.path.exists(INPUT_CAR_IMAGE):
        print(f"❌ ERROR: Input car image '{INPUT_CAR_IMAGE}' not found.")
        return
    if not os.path.exists(CAR_MODEL_XML):
        print(f"❌ ERROR: Car detection model '{CAR_MODEL_XML}' not found.")
        return

    try:
        # Load car image
        print(f"\nLoading car image '{INPUT_CAR_IMAGE}'...")
        img_bgr = cv2.imread(INPUT_CAR_IMAGE)
        if img_bgr is None:
            raise ValueError("OpenCV couldn't read the image.")
        
        # Initialize OpenVINO for car plate detection
        print("\nInitializing OpenVINO Core for car plate detection...")
        core = ov.Core()
        car_model = core.read_model(model=CAR_MODEL_XML)
        compiled_car_model = core.compile_model(model=car_model, device_name="CPU")
        
        # Preprocess car image
        input_blob, original_shape, scale, pad_x, pad_y = preprocess_image_car(
            img_bgr, CAR_INPUT_HEIGHT, CAR_INPUT_WIDTH, CAR_MEAN_BGR, CAR_STD_BGR)
        
        # Run inference for car plate detection
        print("\nRunning car plate detection inference...")
        infer_request = compiled_car_model.create_infer_request()
        infer_request.set_input_tensor(ov.Tensor(input_blob))
        infer_request.infer()
        
        output_dets = infer_request.get_output_tensor(0).data
        output_labels = infer_request.get_output_tensor(1).data
        
        # Process detections
        orig_h, orig_w = original_shape
        best_plate_detection = None
        best_confidence = 0.0
        
        for i in range(output_dets.shape[1]):  # Iterate through detections
            score = output_dets[0, i, 4]
            if score >= CAR_CONFIDENCE_THRESHOLD:
                box_raw = output_dets[0, i, :4]
                
                # Convert to original image coordinates
                box_pad_x_min = box_raw[0] - pad_x
                box_pad_y_min = box_raw[1] - pad_y
                box_pad_x_max = box_raw[2] - pad_x
                box_pad_y_max = box_raw[3] - pad_y
                
                x_min = int(box_pad_x_min / scale)
                y_min = int(box_pad_y_min / scale)
                x_max = int(box_pad_x_max / scale)
                y_max = int(box_pad_y_max / scale)
                
                # Limit coordinates
                x_min = max(0, x_min)
                y_min = max(0, y_min)
                x_max = min(orig_w, x_max)
                y_max = min(orig_h, y_max)
                
                if score > best_confidence:
                    best_confidence = score
                    best_plate_detection = (x_min, y_min, x_max, y_max, score)
        
        # Extract and save plate image
        if best_plate_detection:
            x1, y1, x2, y2, confidence = best_plate_detection
            print(f"\nBest plate detection found (confidence: {confidence:.2f})")
            
            if x1 >= x2 or y1 >= y2:
                raise ValueError("Invalid plate dimensions after adjustment")
            
            plate_crop_bgr = img_bgr[y1:y2, x1:x2]
            if plate_crop_bgr.size == 0:
                raise ValueError("Empty plate crop")
            
            # Correct rotation if needed
            plate_crop_bgr = detect_and_correct_rotation(plate_crop_bgr)
            
            # Save extracted plate
            cv2.imwrite(TEMP_PLATE_IMAGE, plate_crop_bgr)
            print(f"✅ Extracted plate saved to: '{TEMP_PLATE_IMAGE}'")
            
        else:
            print("❌ No license plate detected in the image")
            return

        # --- Stage 2: Read License Plate Text ---
        print("\n=== Stage 2: License Plate Reading ===")
        
        # Load metadata for plate reading
        class_map, preprocess_params = load_metadata()
        if not class_map or not preprocess_params:
            print("❌ Error loading metadata for plate reading")
            return
        
        # Initialize OCR
        print("\nInitializing EasyOCR...")
        ocr_reader = easyocr.Reader(OCR_LANGUAGES, gpu=OCR_GPU)
        
        # Initialize plate reading model
        print("\nInitializing plate reading model...")
        plate_model = core.read_model(model=PLATE_MODEL_XML, weights=PLATE_MODEL_BIN)
        compiled_plate_model = core.compile_model(model=plate_model, device_name="CPU")
        
        # Preprocess plate image
        target_height = preprocess_params['target_height']
        target_width = preprocess_params['target_width']
        mean = preprocess_params['mean']
        std = preprocess_params['std']
        
        input_tensor, original_plate, scaling_meta, padded_plate = preprocess_image_plate(
            TEMP_PLATE_IMAGE, target_height, target_width, mean, std)
        
        if input_tensor is None:
            print("❌ Error preprocessing plate image")
            return
        
        # Run inference for plate reading
        print("\nRunning plate text detection inference...")
        results = compiled_plate_model([input_tensor])
        
        output_dets = results[compiled_plate_model.output("dets")][0]
        output_labels = results[compiled_plate_model.output("labels")][0]
        
        # Process detections
        relevant_detections = []
        
        for i in range(len(output_dets)):
            detection = output_dets[i]
            label_index = int(output_labels[i])
            confidence = detection[4]
            
            if confidence >= PLATE_CONFIDENCE_THRESHOLD:
                class_name = class_map.get(label_index, f"Label_{label_index}")
                
                if class_name in ["num", "tun"]:
                    coords_padded = detection[:4]
                    x1, y1, x2, y2 = scale_coords(coords_padded, scaling_meta, target_height, target_width)
                    
                    if x1 >= x2 or y1 >= y2:
                        print(f"Skipping invalid box for {class_name}")
                        continue
                    
                    relevant_detections.append({
                        'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                        'class_name': class_name,
                        'confidence': confidence,
                        'ocr_text': None
                    })
        
        # Sort detections left-to-right
        sorted_detections = sorted(relevant_detections, key=lambda d: d['x1'])
        
        # Perform OCR on detected numbers
        for det in sorted_detections:
            if det['class_name'] == 'num':
                x1, y1, x2, y2 = det['x1'], det['y1'], det['x2'], det['y2']
                margin = 2
                y1m = max(0, y1 - margin)
                y2m = min(original_plate.shape[0], y2 + margin)
                x1m = max(0, x1 - margin)
                x2m = min(original_plate.shape[1], x2 + margin)
                
                if y1m >= y2m or x1m >= x2m:
                    det['ocr_text'] = "[OCR_CROP_FAIL]"
                    continue
                
                num_crop = original_plate[y1m:y2m, x1m:x2m]
                num_crop_rgb = cv2.cvtColor(num_crop, cv2.COLOR_BGR2RGB)
                
                try:
                    ocr_result_list = ocr_reader.readtext(
                        num_crop_rgb,
                        allowlist=OCR_ALLOWLIST_NUMBERS,
                        detail=0,
                        paragraph=False
                    )
                    ocr_text = "".join(ocr_result_list).strip()
                    det['ocr_text'] = ocr_text if ocr_text else "[NO_DIGITS]"
                except Exception as e:
                    print(f"OCR Error: {e}")
                    det['ocr_text'] = "[OCR_ERROR]"
        
        # Format final output
        detection_sequence = [d['class_name'] for d in sorted_detections]
        print(f"\nDetected sequence: {detection_sequence}")
        
        pattern_num_tun_num = ['num', 'tun', 'num']
        pattern_tun_num = ['tun', 'num']
        pattern_num_tun = ['num', 'tun']
        
        # Determine final plate string
        if len(sorted_detections) == 3 and detection_sequence == pattern_num_tun_num:
            if (sorted_detections[0]['ocr_text'] and sorted_detections[2]['ocr_text'] and
                '[OCR_' not in sorted_detections[0]['ocr_text'] and
                '[OCR_' not in sorted_detections[2]['ocr_text']):
                num1_text = sorted_detections[0]['ocr_text']
                num2_text = sorted_detections[2]['ocr_text']
                final_ocr_string = f"{num1_text} TN {num2_text}"
            else:
                ocr_status1 = sorted_detections[0].get('ocr_text', '[N/A]')
                ocr_status2 = sorted_detections[2].get('ocr_text', '[N/A]')
                final_ocr_string = f"OCR Failed: {ocr_status1} TN {ocr_status2}"
        
        elif len(sorted_detections) == 2:
            if detection_sequence in [pattern_tun_num, pattern_num_tun]:
                num_det = sorted_detections[1] if detection_sequence == pattern_tun_num else sorted_detections[0]
                if num_det['ocr_text'] and '[OCR_' not in num_det['ocr_text']:
                    final_ocr_string = f"RS {num_det['ocr_text']}"
                else:
                    ocr_status = num_det.get('ocr_text', '[N/A]')
                    final_ocr_string = f"OCR Failed: RS {ocr_status}"
            else:
                final_ocr_string = f"Unmatched Sequence: {detection_sequence}"
        else:
            final_ocr_string = "No valid plate pattern detected"
        
        print(f"\n>>> FINAL PLATE STRING: {final_ocr_string} <<<")
        
        # Draw results
        final_image = original_plate.copy()
        for det in sorted_detections:
            x1, y1, x2, y2 = det['x1'], det['y1'], det['x2'], det['y2']
            class_name = det['class_name']
            confidence = det['confidence']
            ocr_text = det.get('ocr_text', '')
            
            color = (0, 255, 0) if class_name == "num" else (0, 0, 255)
            cv2.rectangle(final_image, (x1, y1), (x2, y2), color, 2)
            
            label_text = f"{class_name}: {confidence:.2f}"
            if class_name == 'num' and ocr_text:
                label_text += f" OCR:[{ocr_text}]"
            
            (w, h), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            text_y = y1 - 10 if y1 > 20 else y1 + h + 10
            cv2.rectangle(final_image, (x1, text_y - h - 5), (x1 + w, text_y), color, -1)
            cv2.putText(final_image, label_text, (x1, text_y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        
        cv2.putText(final_image, f"Plate: {final_ocr_string}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
        
        # Save final result
        cv2.imwrite(OUTPUT_FINAL_IMAGE, final_image)
        print(f"\n✅ Final result saved to: '{OUTPUT_FINAL_IMAGE}'")
        
        # Display result
        try:
            cv2.imshow("Final Result", final_image)
            print("\nPress any key to close the image window...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        except Exception as e:
            print(f"Could not display image: {e}")
        
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()