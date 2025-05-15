import cv2
import numpy as np
import json
import time
import os
import easyocr # <-- Import EasyOCR
from openvino.runtime import Core

MODEL_DIR = "model"
MODEL_DIR1 = ""
META_DIR = os.path.join(MODEL_DIR1, "model_meta")

MODEL_XML_PATH = os.path.join(MODEL_DIR, "saved_model.xml")
MODEL_BIN_PATH = os.path.join(MODEL_DIR, "saved_model.bin")
# Choose the correct dm.json file. If it's in the main directory, just use "dm.json"
LABEL_MAP_PATH = os.path.join(META_DIR, "dm.json")
#LABEL_MAP_PATH = "dm.json" # <-- Uncomment this line if dm.json is in the SAME folder as the script

IMAGE_PATH = "n.jpg"
CONFIDENCE_THRESHOLD = 0.54 # User requested confidence threshold
OUTPUT_IMAGE_PATH = "i_detected_ocr.jpg" # Changed output name
SAVE_INSTEAD_OF_SHOW = True # Keep saving instead of showing for now

# --- Preprocessing Parameters ---
INPUT_HEIGHT = 640
INPUT_WIDTH = 640
NORM_MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float32) # R, G, B
NORM_STD = np.array([58.395, 57.12, 57.375], dtype=np.float32)  # R, G, B

# --- EasyOCR Configuration ---
# Initialize EasyOCR Reader once. gpu=False uses CPU.
# Downloads models on first run if needed.
print("Initializing EasyOCR Reader (may download models on first run)...")
try:
    # Include both English ('en') and Arabic ('ar')
    ocr_reader = easyocr.Reader(['en', 'ar'], gpu=False)
    print("EasyOCR Reader initialized.")
except Exception as e:
    print(f"Error initializing EasyOCR: {e}")
    print("Please ensure EasyOCR is installed (`pip install easyocr`) and necessary models can be downloaded.")
    exit(1)

# --- Helper Function for Preprocessing (Unchanged) ---
def preprocess_image(image_path, target_height, target_width, mean, std):
    """Loads and preprocesses an image for the model."""
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Image not found at {image_path}")

    original_h, original_w = image.shape[:2]

    scale_h = target_height / original_h
    scale_w = target_width / original_w
    scale = min(scale_h, scale_w)

    new_h, new_w = int(original_h * scale), int(original_w * scale)
    if new_h <= 0 or new_w <=0:
         raise ValueError(f"Invalid resized dimensions ({new_w}x{new_h}) from original ({original_w}x{original_h}) with scale {scale}")
    resized_image = cv2.resize(image, (new_w, new_h))

    pad_h = target_height - new_h
    pad_w = target_width - new_w
    top, bottom = pad_h // 2, pad_h - (pad_h // 2)
    left, right = pad_w // 2, pad_w - (pad_w // 2)

    padded_image = cv2.copyMakeBorder(
        resized_image, top, bottom, left, right,
        cv2.BORDER_CONSTANT, value=(0, 0, 0)
    )

    rgb_image = cv2.cvtColor(padded_image, cv2.COLOR_BGR2RGB)
    normalized_image = (rgb_image.astype(np.float32) - mean) / std
    chw_image = normalized_image.transpose((2, 0, 1))
    input_tensor = np.expand_dims(chw_image, axis=0)

    return input_tensor, original_h, original_w, scale, top, left

# --- Main Execution ---
if __name__ == "__main__":
    # 1. Load Label Map
    if not os.path.exists(LABEL_MAP_PATH):
        print(f"Error: Label map file not found at {LABEL_MAP_PATH}")
        alt_label_path = "dm.json"
        if os.path.exists(alt_label_path):
            print(f"Attempting to load from alternative path: {alt_label_path}")
            LABEL_MAP_PATH = alt_label_path
        else:
             exit(1)
    try:
        with open(LABEL_MAP_PATH, 'r') as f:
            label_map = json.load(f)
            class_id_to_name = {int(k): v['name'] for k, v in label_map.items()}
        print(f"Loaded label map with {len(class_id_to_name)} classes from {LABEL_MAP_PATH}.")
    except Exception as e:
        print(f"Error loading label map from {LABEL_MAP_PATH}: {e}")
        exit(1)

    # 2. Initialize OpenVINO Core
    print("Initializing OpenVINO Runtime...")
    core = Core()

    # 3. Load and Compile Model
    print(f"Loading model: {MODEL_XML_PATH}")
    if not os.path.exists(MODEL_XML_PATH) or not os.path.exists(MODEL_BIN_PATH):
        print(f"Error: Model XML or BIN file not found in {MODEL_DIR}")
        exit(1)
    start_load = time.time()
    try:
        model = core.read_model(model=MODEL_XML_PATH, weights=MODEL_BIN_PATH)
    except Exception as e:
        print(f"Error reading OpenVINO model: {e}")
        exit(1)
    input_layer = model.input(0)
    try:
        output_dets_layer_name = "dets"
        output_labels_layer_name = "labels"
        output_dets_layer = model.output(output_dets_layer_name)
        output_labels_layer = model.output(output_labels_layer_name)
    except Exception as e:
        print(f"Error finding output layers '{output_dets_layer_name}' or '{output_labels_layer_name}': {e}")
        print("Available outputs:", [out.get_any_name() for out in model.outputs])
        exit(1)
    print(f"  Input Layer Info: {input_layer}")
    print(f"  Output 'dets' Layer Info: {output_dets_layer}")
    print(f"  Output 'labels' Layer Info: {output_labels_layer}")
    print("Compiling model for CPU...")
    try:
        compiled_model = core.compile_model(model=model, device_name="CPU")
    except Exception as e:
        print(f"Error compiling model: {e}")
        exit(1)
    load_time = time.time() - start_load
    print(f"Model loaded and compiled in {load_time:.4f} seconds.")

    # 4. Load and Preprocess Image
    print(f"Loading and preprocessing image: {IMAGE_PATH}")
    try:
        input_tensor, orig_h, orig_w, scale, pad_top, pad_left = preprocess_image(
            IMAGE_PATH, INPUT_HEIGHT, INPUT_WIDTH, NORM_MEAN, NORM_STD
        )
        # Load original image separately for OCR and drawing
        image_for_ocr = cv2.imread(IMAGE_PATH)
        output_image = image_for_ocr.copy() # Copy for drawing boxes later
        if image_for_ocr is None:
             raise FileNotFoundError(f"Image not found at {IMAGE_PATH}")
    except FileNotFoundError as e:
        print(e)
        exit(1)
    except Exception as e:
         print(f"Error during image loading/preprocessing: {e}")
         exit(1)
    print("Preprocessing complete.")

    # 5. Run Inference
    print("Running inference...")
    start_infer = time.time()
    try:
        # Get descriptors *before* inference if using them as keys
        output_dets_node = compiled_model.output(output_dets_layer_name)
        output_labels_node = compiled_model.output(output_labels_layer_name)
        results = compiled_model(input_tensor)
    except Exception as e:
        print(f"Error during model inference: {e}")
        exit(1)
    infer_time = time.time() - start_infer
    print(f"Inference finished in {infer_time:.4f} seconds.")

    # 6. Post-process Results & Perform OCR
    ocr_results = { "id": "N/A", "lastname": "N/A", "name": "N/A" } # Initialize results
    try:
        output_dets = results[output_dets_node]
        output_labels = results[output_labels_node]
    except Exception as e:
        print(f"Error accessing results using output nodes: {e}")
        exit(1)

    if output_dets.shape[0] != 1 or output_labels.shape[0] != 1:
        print(f"Warning: Expected batch size of 1, but got shapes {output_dets.shape} and {output_labels.shape}")
        detections = []
        labels = []
        if output_dets.shape[0] > 0 and output_labels.shape[0] > 0: # Try using first batch if exists
            detections = output_dets[0]
            labels = output_labels[0]
    else:
        detections = output_dets[0]
        labels = output_labels[0]

    print(f"Raw detections count: {len(detections)}")
    num_filtered_detections = 0

    for i, detection in enumerate(detections):
        if i >= len(labels):
            print(f"Warning: Detection index {i} out of bounds for labels array (length {len(labels)}). Skipping.")
            continue

        x1, y1, x2, y2, score = detection
        label_index = int(labels[i])

        if score >= CONFIDENCE_THRESHOLD:
            num_filtered_detections += 1
            class_name = class_id_to_name.get(label_index, f"Label_{label_index}")

            # --- Convert coordinates back to original image space ---
            orig_x1 = x1 - pad_left
            orig_y1 = y1 - pad_top
            orig_x2 = x2 - pad_left
            orig_y2 = y2 - pad_top

            orig_x1 /= scale
            orig_y1 /= scale
            orig_x2 /= scale
            orig_y2 /= scale

            orig_x1 = max(0, int(orig_x1))
            orig_y1 = max(0, int(orig_y1))
            orig_x2 = min(orig_w, int(orig_x2))
            orig_y2 = min(orig_h, int(orig_y2))

            if orig_x1 >= orig_x2 or orig_y1 >= orig_y2:
                 print(f"Warning: Invalid coordinates after conversion for {class_name} (Index {i}). Skipping.")
                 continue

            # --- Crop the detected region for OCR from the *original* image ---
            try:
                # Add a small margin for better OCR, ensuring it stays within bounds
                margin = 5
                crop_y1 = max(0, orig_y1 - margin)
                crop_y2 = min(orig_h, orig_y2 + margin)
                crop_x1 = max(0, orig_x1 - margin)
                crop_x2 = min(orig_w, orig_x2 + margin)

                if crop_y1 >= crop_y2 or crop_x1 >= crop_x2:
                    print(f"Warning: Invalid crop dimensions for {class_name} (Index {i}). Skipping OCR.")
                    continue

                cropped_image = image_for_ocr[crop_y1:crop_y2, crop_x1:crop_x2]

                # --- Perform OCR based on class name ---
                ocr_text = "OCR Failed"
                if class_name == 'id':
                    # English, digits only
                    print(f"Running OCR (en, digits) for '{class_name}'...")
                    ocr_result_list = ocr_reader.readtext(cropped_image, allowlist='0123456789', detail=0, paragraph=True)
                    ocr_text = " ".join(ocr_result_list) if ocr_result_list else "No Digits Found"
                    ocr_results['id'] = ocr_text
                elif class_name == 'lastname' or class_name == 'name':
                     # Arabic
                    print(f"Running OCR (ar) for '{class_name}'...")
                    ocr_result_list = ocr_reader.readtext(cropped_image, detail=0, paragraph=True) # EasyOCR handles language selection
                    ocr_text = " ".join(ocr_result_list) if ocr_result_list else "No Arabic Text Found"
                    ocr_results[class_name] = ocr_text # Store based on detected name

                print(f"  > OCR Result for {class_name}: {ocr_text}")

            except Exception as ocr_e:
                print(f"Error during OCR for {class_name} (Index {i}): {ocr_e}")
                ocr_results[class_name] = "OCR Exception" # Record the error

            # --- Draw bounding box and label on the output image ---
            color = (0, 255, 0) # Green
            cv2.rectangle(output_image, (orig_x1, orig_y1), (orig_x2, orig_y2), color, 2)
            label_text = f"{class_name}: {score:.2f}"
            (text_width, text_height), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            label_y = max(orig_y1, text_height + 5)
            cv2.rectangle(output_image, (orig_x1, label_y - text_height - baseline), (orig_x1 + text_width, label_y), color, -1)
            cv2.putText(output_image, label_text, (orig_x1, label_y - baseline // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)


    print(f"\nDetections after filtering (threshold > {CONFIDENCE_THRESHOLD}): {num_filtered_detections}")

    # --- Print Final OCR Results ---
    print("\n--- Extracted OCR Information ---")
    print(f"ID:       {ocr_results.get('id', 'Not Detected')}")
    print(f"Lastname: {ocr_results.get('lastname', 'Not Detected')}")
    print(f"Name:     {ocr_results.get('name', 'Not Detected')}")
    print("-------------------------------")

    # 7. Display or Save Results
    if SAVE_INSTEAD_OF_SHOW:
        try:
            cv2.imwrite(OUTPUT_IMAGE_PATH, output_image)
            print(f"Output image with detections saved to: {OUTPUT_IMAGE_PATH}")
        except Exception as save_e:
             print(f"Error saving output image: {save_e}")
    else:
        try:
            print("Displaying results (press any key to close)...")
            cv2.imshow("Detections", output_image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        except cv2.error as e:
            print("\nERROR: Failed to display image using cv2.imshow(). Saving instead.")
            print(f"(OpenCV Error: {e})")
            cv2.imwrite(OUTPUT_IMAGE_PATH, output_image)
            print(f"Output image saved to: {OUTPUT_IMAGE_PATH} as fallback.")

    print("\nScript finished.")