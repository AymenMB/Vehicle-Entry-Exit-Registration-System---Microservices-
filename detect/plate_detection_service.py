import openvino as ov
import numpy as np
import cv2
import easyocr
import yaml
import json
import logging
import sys
import os
import time
from concurrent import futures
import grpc
import io
import traceback

# Import the generated grpc modules
# Ensure the protos directory is discoverable
proto_dir = os.path.join(os.path.dirname(__file__), 'protos')
if proto_dir not in sys.path:
    sys.path.append(proto_dir)
# Ensure the parent directory (containing protos/) is discoverable if running scripts from detect/
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
     sys.path.append(parent_dir)

# Now import
try:
    from protos import plate_detection_pb2, plate_detection_pb2_grpc
except ImportError as e:
    print(f"Error importing protobuf modules: {e}")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)


# Path configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("plate_detection_service")

# --- Helper Functions (Adapted from platef.py) ---

# --- Commented out or removed load_metadata if not using Stage 2 ---
# def load_metadata(...): ...

def preprocess_image_car(image, target_height, target_width, mean, std):
    """Preprocess image for car plate detection (Stage 1)."""
    try:
        original_height, original_width = image.shape[:2]
        scale_h = target_height / original_height
        scale_w = target_width / original_width
        scale = min(scale_h, scale_w)
        new_height = int(round(original_height * scale))
        new_width = int(round(original_width * scale))

        resized_image = cv2.resize(image, (new_width, new_height))

        # Create padded image (using mean values might be better than 0s)
        # Using 0s as per platef.py for now
        padded_image = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        pad_top = (target_height - new_height) // 2
        pad_left = (target_width - new_width) // 2
        padded_image[pad_top:pad_top + new_height, pad_left:pad_left + new_width] = resized_image

        # Normalize and transpose
        blob = padded_image.astype(np.float32)
        blob -= mean
        blob /= std
        blob = blob.transpose(2, 0, 1)  # HWC to CHW
        blob = np.expand_dims(blob, axis=0)  # Add batch dimension NCHW

        scaling_meta = {
            'original_height': original_height,
            'original_width': original_width,
            'scale': scale,
            'pad_top': pad_top,
            'pad_left': pad_left
        }
        return blob, scaling_meta
    except Exception as e:
        logger.error(f"Error in preprocess_image_car: {e}", exc_info=True)
        raise

# --- RENAMED this function ---
def scale_coords_car(coords, scaling_meta):
    """Scale coordinates from padded/resized Stage 1 input back to original image."""
    try:
        x_min, y_min, x_max, y_max = coords
        pad_left = scaling_meta['pad_left']
        pad_top = scaling_meta['pad_top']
        scale = scaling_meta['scale']
        orig_h = scaling_meta['original_height']
        orig_w = scaling_meta['original_width']

        # Remove padding
        x_min_unpad = x_min - pad_left
        y_min_unpad = y_min - pad_top
        x_max_unpad = x_max - pad_left
        y_max_unpad = y_max - pad_top

        # Scale back to original
        if scale == 0: return 0, 0, 0, 0 # Avoid division by zero

        orig_x_min = x_min_unpad / scale
        orig_y_min = y_min_unpad / scale
        orig_x_max = x_max_unpad / scale
        orig_y_max = y_max_unpad / scale

        # Clip coordinates to original image bounds
        orig_x_min = max(0, min(orig_x_min, orig_w))
        orig_y_min = max(0, min(orig_y_min, orig_h))
        orig_x_max = max(0, min(orig_x_max, orig_w))
        orig_y_max = max(0, min(orig_y_max, orig_h))

        return int(orig_x_min), int(orig_y_min), int(orig_x_max), int(orig_y_max)
    except Exception as e:
        logger.error(f"Error in scale_coords_car: {e}", exc_info=True) # Updated log message
        raise

def detect_and_correct_rotation(plate_img):
    """Detect and correct plate rotation if needed."""
    try:
        ANGLE_THRESHOLD = 2.0 # As defined in platef.py

        if plate_img is None or plate_img.size == 0:
            logger.warning("Cannot correct rotation on empty image.")
            return plate_img

        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        # Apply Gaussian blur to reduce noise
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        # Use adaptive thresholding
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            logger.debug("No contours found for rotation correction.")
            return plate_img # Return original if no contours

        # Find the largest contour
        c = max(contours, key=cv2.contourArea)
        # Get the minimum area rectangle
        rect = cv2.minAreaRect(c)
        angle = rect[2] # Angle is the third element

        # Normalize the angle
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
             angle = angle - 90 # Corrected logic from platef.py

        # Only rotate if angle exceeds threshold
        if abs(angle) < ANGLE_THRESHOLD:
            logger.debug(f"Plate angle {angle:.2f} within threshold, no rotation applied.")
            return plate_img

        logger.info(f"Detected plate angle: {angle:.2f}. Applying rotation correction.")
        h, w = plate_img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        # Use BORDER_REPLICATE to avoid black borders if possible
        rotated = cv2.warpAffine(plate_img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        return rotated
    except Exception as e:
        logger.error(f"Error in detect_and_correct_rotation: {e}", exc_info=True)
        return plate_img # Return original image on error

# --- gRPC Servicer Implementation ---
class PlateDetectionServicer(plate_detection_pb2_grpc.PlateDetectionServiceServicer):
    """
    gRPC server for license plate detection, based on platef.py logic.
    Performs Stage 1 (Plate Area Detection) and Stage 3 (OCR on Crop).
    """
    def __init__(self):
        # --- Configuration Constants ---
        self.SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        # Car Plate Detection (Stage 1)
        self.CAR_MODEL_XML = os.path.join(self.SCRIPT_DIR, "model_platecar/model/saved_model.xml")
        self.CAR_INPUT_HEIGHT = 640
        self.CAR_INPUT_WIDTH = 640
        self.CAR_MEAN_BGR = np.array([103.53, 116.28, 123.675], dtype=np.float32)
        self.CAR_STD_BGR = np.array([57.375, 57.12, 58.395], dtype=np.float32)
        self.CAR_CONFIDENCE_THRESHOLD = 0.53
        # Plate Reading (Stage 2)
        self.PLATE_BASE_FOLDER = os.path.join(self.SCRIPT_DIR, "plate_ex")
        self.PLATE_MODEL_XML = os.path.join(self.PLATE_BASE_FOLDER, "model", "saved_model.xml")
        self.PLATE_MODEL_BIN = os.path.join(self.PLATE_BASE_FOLDER, "model", "saved_model.bin")
        self.PLATE_DM_JSON = os.path.join(self.PLATE_BASE_FOLDER, "model_meta", "dm.json")
        self.PLATE_TRANSFORMS_YAML = os.path.join(self.PLATE_BASE_FOLDER, "model_meta", "transforms.yaml")
        self.PLATE_CONFIDENCE_THRESHOLD = 0.54
        # OCR Configuration (Stage 3)
        self.OCR_LANGUAGES = ['en']
        self.OCR_ALLOWLIST = '0123456789'
        self.OCR_GPU = False

        logger.info("Initializing PlateDetectionServicer...")
        # --- Initialize OpenVINO ---
        logger.info("Initializing OpenVINO Core...")
        self.core = ov.Core()

        # --- Load Car Detection Model (Stage 1) ---
        logger.info(f"Loading car detection model: {self.CAR_MODEL_XML}")
        if not os.path.exists(self.CAR_MODEL_XML):
             raise FileNotFoundError(f"Car detection model not found: {self.CAR_MODEL_XML}")
        self.car_model = self.core.read_model(model=self.CAR_MODEL_XML)
        logger.info("Compiling car detection model for CPU...")
        self.compiled_car_model = self.core.compile_model(model=self.car_model, device_name="CPU")
        self.car_output_node_dets = self.compiled_car_model.outputs[0]
        logger.info("Car detection model loaded and compiled.")

        # --- Load Plate Reading Model (Stage 2) - RESTORED ---
        self.compiled_plate_model = None
        self.class_map = None
        self.plate_preprocess_params = None
        try:
            logger.info(f"Loading plate reading model: {self.PLATE_MODEL_XML}")
            if not os.path.exists(self.PLATE_MODEL_XML) or not os.path.exists(self.PLATE_MODEL_BIN):
                raise FileNotFoundError("Plate reading model/weights not found.")
            self.plate_model = self.core.read_model(model=self.PLATE_MODEL_XML, weights=self.PLATE_MODEL_BIN)
            logger.info("Compiling plate reading model for CPU...")
            self.compiled_plate_model = self.core.compile_model(model=self.plate_model, device_name="CPU")
            self.plate_output_node_dets = self.compiled_plate_model.output("dets")
            self.plate_output_node_labels = self.compiled_plate_model.output("labels")
            logger.info("Plate reading model loaded and compiled.")

            # --- FIX: Call load_metadata as a method ---
            self.class_map, self.plate_preprocess_params = self.load_metadata(self.PLATE_DM_JSON, self.PLATE_TRANSFORMS_YAML)
            if not self.class_map or not self.plate_preprocess_params:
                raise ValueError("Failed to load metadata for plate reading model.")
        except Exception as e:
            logger.error(f"Could not load Stage 2 model or metadata: {e}. This might prevent correct plate formatting.", exc_info=True)
            raise ValueError("Failed to load Stage 2 model/metadata.") from e

        # --- Initialize EasyOCR (Stage 3) ---
        logger.info(f"Initializing EasyOCR for languages: {self.OCR_LANGUAGES} (GPU: {self.OCR_GPU})...")
        try:
            self.ocr_reader = easyocr.Reader(self.OCR_LANGUAGES, gpu=self.OCR_GPU)
            logger.info("EasyOCR initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}", exc_info=True)
            raise RuntimeError("EasyOCR initialization failed") from e

        logger.info("PlateDetectionServicer initialization complete.")

    # --- Helper Functions (Defined as Methods) ---

    def load_metadata(self, dm_json_path, transforms_yaml_path):
        """Load metadata for the plate reading model (Stage 2)."""
        class_map = None
        preprocess_params = {} # Initialize empty dict
        try:
            # Load class mapping
            with open(dm_json_path, 'r') as f:
                dm_data = json.load(f)
            class_map = {int(k): v['name'] for k, v in dm_data.items()}
            logger.info(f"Loaded class map from {dm_json_path}")

            # Load preprocessing parameters from transforms.yaml
            with open(transforms_yaml_path, 'r') as f:
                transforms_config = yaml.safe_load(f)
            transform_list = transforms_config.get('valid', []) or transforms_config.get('train', [])
            if not transform_list:
                 logger.warning(f"Could not find 'valid' or 'train' transform list in {transforms_yaml_path}")
            # Find RescaleWithPadding
            for transform in transform_list:
                if 'RescaleWithPadding' in transform:
                    preprocess_params['target_height'] = transform['RescaleWithPadding']['height']
                    preprocess_params['target_width'] = transform['RescaleWithPadding']['width']
                    break
            # Find NormalizeMeanStd
            for transform in transform_list:
                if 'NormalizeMeanStd' in transform:
                    preprocess_params['mean'] = np.array(transform['NormalizeMeanStd']['mean'], dtype=np.float32)
                    preprocess_params['std'] = np.array(transform['NormalizeMeanStd']['std'], dtype=np.float32)
                    break
            # Set defaults if not found
            if 'target_height' not in preprocess_params:
                preprocess_params['target_height'] = 640 # Default
                preprocess_params['target_width'] = 640 # Default
                logger.warning("RescaleWithPadding not found in transforms, using default 640x640.")
            if 'mean' not in preprocess_params:
                preprocess_params['mean'] = np.array([0,0,0], dtype=np.float32) # Default
                preprocess_params['std'] = np.array([1,1,1], dtype=np.float32) # Default
                logger.warning("NormalizeMeanStd not found in transforms, using default mean=[0,0,0], std=[1,1,1].")

            logger.info(f"Loaded metadata: {len(class_map) if class_map else 0} classes, preprocess params: {preprocess_params}")
            return class_map, preprocess_params
        except Exception as e:
            logger.error(f"Error loading metadata: {e}", exc_info=True)
            return None, None


    def preprocess_image_car(self, image, target_height, target_width, mean, std):
        """Preprocess image for car plate detection (Stage 1)."""
        try:
            original_height, original_width = image.shape[:2]
            scale_h = target_height / original_height
            scale_w = target_width / original_width
            scale = min(scale_h, scale_w)
            new_height = int(round(original_height * scale))
            new_width = int(round(original_width * scale))

            resized_image = cv2.resize(image, (new_width, new_height))

            padded_image = np.zeros((target_height, target_width, 3), dtype=np.uint8)
            pad_top = (target_height - new_height) // 2
            pad_left = (target_width - new_width) // 2
            padded_image[pad_top:pad_top + new_height, pad_left:pad_left + new_width] = resized_image

            blob = padded_image.astype(np.float32)
            blob -= mean
            blob /= std
            blob = blob.transpose(2, 0, 1)
            blob = np.expand_dims(blob, axis=0)

            scaling_meta = {
                'original_height': original_height, 'original_width': original_width,
                'scale': scale, 'pad_top': pad_top, 'pad_left': pad_left
            }
            return blob, scaling_meta
        except Exception as e:
            logger.error(f"Error in preprocess_image_car: {e}", exc_info=True)
            raise


    def scale_coords_car(self, box_raw, scaling_meta):
        """Scale car detection box back to original image coordinates."""
        try:
            orig_h, orig_w = scaling_meta['original_height'], scaling_meta['original_width']
            scale = scaling_meta['scale']
            pad_left = scaling_meta['pad_left']
            pad_top = scaling_meta['pad_top']

            box_pad_x_min = box_raw[0] - pad_left
            box_pad_y_min = box_raw[1] - pad_top
            box_pad_x_max = box_raw[2] - pad_left
            box_pad_y_max = box_raw[3] - pad_top

            if scale == 0: return 0, 0, 0, 0
            x_min = int(box_pad_x_min / scale)
            y_min = int(box_pad_y_min / scale)
            x_max = int(box_pad_x_max / scale)
            y_max = int(box_pad_y_max / scale)

            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(orig_w, x_max)
            y_max = min(orig_h, y_max)

            return x_min, y_min, x_max, y_max
        except Exception as e:
            logger.error(f"Error in scale_coords_car: {e}", exc_info=True)
            raise


    def detect_and_correct_rotation(self, plate_img):
        """Detect and correct plate rotation if needed."""
        try:
            ANGLE_THRESHOLD = 2.0
            if plate_img is None or plate_img.size == 0: return plate_img
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours: return plate_img
            c = max(contours, key=cv2.contourArea)
            rect = cv2.minAreaRect(c)
            angle = rect[2]
            if angle < -45: angle = 90 + angle
            elif angle > 45: angle = angle - 90
            if abs(angle) < ANGLE_THRESHOLD: return plate_img
            logger.info(f"Detected plate angle: {angle:.2f}. Applying rotation correction.")
            h, w = plate_img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(plate_img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            return rotated
        except Exception as e:
            logger.error(f"Error in detect_and_correct_rotation: {e}", exc_info=True)
            return plate_img


    def preprocess_image_plate(self, image, target_h, target_w, mean, std):
        """Preprocess image for plate reading (Stage 2)."""
        try:
            original_h, original_w = image.shape[:2]
            scale = min(target_h / original_h, target_w / original_w)
            new_h, new_w = int(original_h * scale), int(original_w * scale)
            resized_img = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

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
                'original_h': original_h, 'original_w': original_w,
                'scale': scale, 'top_pad': top_pad, 'left_pad': left_pad
            }
            return input_tensor, scaling_meta, padded_img # Return padded_img if needed for viz
        except Exception as e:
            logger.error(f"Error in preprocess_image_plate: {e}", exc_info=True)
            raise


    def scale_coords_plate(self, coords_padded, scaling_meta):
        """Scale plate character coordinates back to the original *cropped* plate image."""
        try:
            x_min, y_min, x_max, y_max = coords_padded
            orig_h, orig_w = scaling_meta['original_h'], scaling_meta['original_w']
            scale = scaling_meta['scale']
            left_pad = scaling_meta['left_pad']
            top_pad = scaling_meta['top_pad']

            x_min_unpad = x_min - left_pad
            y_min_unpad = y_min - top_pad
            x_max_unpad = x_max - left_pad
            y_max_unpad = y_max - top_pad

            if scale == 0: return 0, 0, 0, 0
            orig_x_min = x_min_unpad / scale
            orig_y_min = y_min_unpad / scale
            orig_x_max = x_max_unpad / scale
            orig_y_max = y_max_unpad / scale

            orig_x_min = max(0, int(orig_x_min))
            orig_y_min = max(0, int(orig_y_min))
            orig_x_max = min(orig_w, int(orig_x_max))
            orig_y_max = min(orig_h, int(orig_y_max))

            return orig_x_min, orig_y_min, orig_x_max, orig_y_max
        except Exception as e:
            logger.error(f"Error in scale_coords_plate: {e}", exc_info=True)
            raise


    # --- Main Detection Logic ---
    def _perform_detection(self, image_bytes):
        """Internal method - Stage 1 + Stage 2 + OCR on Chars + Assembly."""
        try:
            # 1. Decode Image
            logger.debug("Decoding image bytes...")
            nparr = np.frombuffer(image_bytes, np.uint8)
            image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image_bgr is None:
                return "", 0.0, "Failed to decode image bytes."
            logger.info(f"Successfully decoded image. Shape: {image_bgr.shape}")
            img_h, img_w = image_bgr.shape[:2]


            # 2. Preprocess for Stage 1 (Car Detection Model)
            logger.debug("Preprocessing image for car detection...")
            # --- FIX: Ensure scaling_meta_car is captured ---
            input_blob_car, scaling_meta_car = self.preprocess_image_car(
                image_bgr, self.CAR_INPUT_HEIGHT, self.CAR_INPUT_WIDTH, self.CAR_MEAN_BGR, self.CAR_STD_BGR
            )

            # 3. Run Stage 1 Inference
            logger.debug("Running car detection inference...")
            # --- FIX: Use defined output node ---
            results_car = self.compiled_car_model({0: input_blob_car})
            logger.info("Car model inference complete.")

            # 4. Post-process Stage 1 Results
            # --- FIX: Use defined output node ---
            output_dets_car_tensor = results_car[self.car_output_node_dets]
            output_dets_car = np.array(output_dets_car_tensor.data)
            logger.info(f"Car model output tensor shape: {output_dets_car.shape}, dtype: {output_dets_car.dtype}")

            if not (len(output_dets_car.shape) == 3 and output_dets_car.shape[0] == 1 and output_dets_car.shape[2] == 5):
                return "", 0.0, f"Unexpected car model output shape: {output_dets_car.shape}. Expected (1, N, 5)."

            num_detections = output_dets_car.shape[1]
            logger.info(f"Number of potential plate detections: {num_detections}")
            detections = output_dets_car[0]

            best_plate_crop = None
            max_confidence_stage1 = 0.0

            for i in range(num_detections):
                detection_data = detections[i]
                if not isinstance(detection_data, np.ndarray) or detection_data.shape != (5,):
                    logger.warning(f"Skipping detection {i} due to unexpected data format.")
                    continue
                confidence = detection_data[4]

                if confidence > self.CAR_CONFIDENCE_THRESHOLD:
                    x_min, y_min, x_max, y_max = map(int, detection_data[:4])
                    # --- FIX: Call scale_coords_car correctly ---
                    orig_coords = self.scale_coords_car((x_min, y_min, x_max, y_max), scaling_meta_car)
                    orig_x_min, orig_y_min, orig_x_max, orig_y_max = orig_coords

                    if orig_x_max > orig_x_min and orig_y_max > orig_y_min:
                        plate_crop = image_bgr[orig_y_min:orig_y_max, orig_x_min:orig_x_max]
                        if plate_crop.size > 0:
                             if confidence > max_confidence_stage1:
                                max_confidence_stage1 = confidence
                                best_plate_crop = plate_crop
                                logger.debug(f"Found better plate candidate (Detection {i}, Conf: {confidence:.3f})")

            if best_plate_crop is None:
                return "", 0.0, "No plate detected with sufficient confidence in Stage 1."

            logger.info(f"Best plate candidate found (Stage 1 Conf: {max_confidence_stage1:.4f}). Size: {best_plate_crop.shape}")

            # 5. Correct Plate Rotation
            logger.debug("Applying rotation correction to plate crop...")
            corrected_plate_crop = self.detect_and_correct_rotation(best_plate_crop)
            if corrected_plate_crop is None or corrected_plate_crop.size == 0:
                 logger.warning("Rotation correction resulted in empty image, using original crop.")
                 corrected_plate_crop = best_plate_crop

            # --- RESTORED: Stage 2 - Character Detection ---
            if not self.compiled_plate_model: # Check if Stage 2 model loaded
                 return "", max_confidence_stage1, "Stage 2 model not available for character detection."

            logger.info("Preprocessing corrected plate for character reading (Stage 2)...")
            # --- FIX: Ensure scaling_meta_plate is captured ---
            input_tensor_plate, scaling_meta_plate, _ = self.preprocess_image_plate(
                corrected_plate_crop,
                self.plate_preprocess_params['target_height'],
                self.plate_preprocess_params['target_width'],
                self.plate_preprocess_params['mean'],
                self.plate_preprocess_params['std']
            )

            logger.info("Running plate reading model inference (Stage 2)...")
            # --- FIX: Use defined output nodes ---
            results_plate = self.compiled_plate_model({0: input_tensor_plate})
            logger.info("Plate reading model inference complete.")

            # --- Post-process Plate Reading Results ---
            output_dets_plate_tensor = results_plate[self.plate_output_node_dets]
            output_labels_plate_tensor = results_plate[self.plate_output_node_labels]
            output_dets_plate = np.array(output_dets_plate_tensor.data)[0]
            output_labels_plate = np.array(output_labels_plate_tensor.data)[0]
            logger.info(f"Stage 2 output shapes: dets={output_dets_plate.shape}, labels={output_labels_plate.shape}")

            relevant_detections = []
            avg_stage2_confidence = 0.0
            num_relevant_dets = 0

            for i in range(len(output_dets_plate)):
                detection = output_dets_plate[i]
                label_index = int(output_labels_plate[i])
                confidence = detection[4]

                if confidence >= self.PLATE_CONFIDENCE_THRESHOLD:
                    class_name = self.class_map.get(label_index, f"Label_{label_index}")
                    if class_name in ["num", "tun"]:
                        coords_padded = detection[:4]
                        # --- FIX: Call scale_coords_plate correctly ---
                        x1, y1, x2, y2 = self.scale_coords_plate(coords_padded, scaling_meta_plate)
                        if x1 < x2 and y1 < y2:
                            relevant_detections.append({
                                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                                'class_name': class_name, 'confidence': confidence, 'ocr_text': None
                            })
                            avg_stage2_confidence += confidence
                            num_relevant_dets += 1
                        # else: logger.warning(...)

            if not relevant_detections:
                return "", max_confidence_stage1, "No characters detected in Stage 2"

            avg_stage2_confidence = avg_stage2_confidence / num_relevant_dets if num_relevant_dets > 0 else 0.0
            overall_confidence = (max_confidence_stage1 + avg_stage2_confidence) / 2
            sorted_detections = sorted(relevant_detections, key=lambda d: d['x1'])
            logger.info(f"Found {len(sorted_detections)} sorted relevant Stage 2 detections.")

            # === Stage 3: Perform OCR on 'num' Characters ===
            logger.info(f"Performing OCR on 'num' characters (Allowlist: '{self.OCR_ALLOWLIST}')...")
            for det in sorted_detections:
                if det['class_name'] == 'num': # Only OCR 'num'
                    x1, y1, x2, y2 = det['x1'], det['y1'], det['x2'], det['y2']
                    margin = 2
                    crop_h, crop_w = corrected_plate_crop.shape[:2]
                    y1m, y2m = max(0, y1 - margin), min(crop_h, y2 + margin)
                    x1m, x2m = max(0, x1 - margin), min(crop_w, x2 + margin)

                    if y1m >= y2m or x1m >= x2m:
                        det['ocr_text'] = "[OCR_CROP_FAIL]"
                        logger.warning(f"OCR crop failed for 'num' at [{x1},{y1},{x2},{y2}]")
                        continue
                    char_crop = corrected_plate_crop[y1m:y2m, x1m:x2m]
                    try:
                        ocr_result_list = self.ocr_reader.readtext(
                            char_crop, allowlist=self.OCR_ALLOWLIST, detail=0, paragraph=False
                        )
                        ocr_text = "".join(ocr_result_list).strip().replace(" ", "")
                        det['ocr_text'] = ocr_text if ocr_text else "[NO_DIGITS]"
                        logger.debug(f"OCR for 'num' box [{x1},{y1},{x2},{y2}] -> '{ocr_text}'")
                    except Exception as ocr_err:
                        logger.error(f"EasyOCR Error on char crop: {ocr_err}", exc_info=True)
                        det['ocr_text'] = "[OCR_ERROR]"

            # === Stage 4: Assemble Final Plate String ===
            logger.info("Assembling final plate string based on Stage 2 sequence and OCR...")
            detection_sequence = [d['class_name'] for d in sorted_detections]
            logger.info(f"Detected sequence: {detection_sequence}")
            pattern_num_tun_num = ['num', 'tun', 'num']
            final_plate_string = ""
            error_occurred = False
            error_message_assembly = ""

            # --- Logic for 'num', 'tun', 'num' ---
            if detection_sequence == pattern_num_tun_num:
                if len(sorted_detections) == 3:
                    ocr1 = sorted_detections[0].get('ocr_text')
                    ocr2 = sorted_detections[2].get('ocr_text')
                    if ocr1 and ocr2 and '[OCR' not in ocr1 and '[NO' not in ocr1 and \
                       '[OCR' not in ocr2 and '[NO' not in ocr2:
                        final_plate_string = f"{ocr1} TN {ocr2}"
                    else:
                        failed_parts = []
                        if not ocr1 or '[OCR' in ocr1 or '[NO' in ocr1: failed_parts.append("first number")
                        if not ocr2 or '[OCR' in ocr2 or '[NO' in ocr2: failed_parts.append("second number")
                        error_message_assembly = f"OCR failed on {', '.join(failed_parts)}"
                        final_plate_string = f"OCR Incomplete: {ocr1 or '[N/A]'} TN {ocr2 or '[N/A]'}"
                        error_occurred = True
                else:
                    error_message_assembly = "Detection count mismatch for num-tun-num pattern"
                    error_occurred = True

            # --- CORRECTED: Logic for 'num', 'tun' (e.g., RS plates) ---
            elif detection_sequence == ['num', 'tun']: # Check for the correct order
                if len(sorted_detections) == 2:
                    # OCR should be on the FIRST element (index 0), which is 'num'
                    ocr_num = sorted_detections[0].get('ocr_text')
                    if ocr_num and '[OCR' not in ocr_num and '[NO' not in ocr_num:
                        final_plate_string = f"RS {ocr_num}" # Format as RS plate
                        logger.info(f"Formatted as RS plate: {final_plate_string}")
                    else:
                        error_message_assembly = "OCR failed on number part for RS-style plate"
                        final_plate_string = f"RS OCR Error: {ocr_num or '[N/A]'}"
                        error_occurred = True
                else:
                    error_message_assembly = "Detection count mismatch for num-tun pattern"
                    error_occurred = True

            # --- Keep the logic for 'tun', 'num' just in case ---
            elif detection_sequence == ['tun', 'num']:
                if len(sorted_detections) == 2:
                    # OCR should be on the second element (index 1), which is 'num'
                    ocr_num = sorted_detections[1].get('ocr_text')
                    if ocr_num and '[OCR' not in ocr_num and '[NO' not in ocr_num:
                        final_plate_string = f"RS {ocr_num}" # Format as RS plate
                        logger.info(f"Formatted as RS plate: {final_plate_string}")
                    else:
                        error_message_assembly = "OCR failed on number part for RS-style plate"
                        final_plate_string = f"RS OCR Error: {ocr_num or '[N/A]'}"
                        error_occurred = True
                else:
                    error_message_assembly = "Detection count mismatch for tun-num pattern"
                    error_occurred = True

            else: # Unrecognized pattern
                 logger.warning(f"Unrecognized plate pattern: {detection_sequence}.")
                 error_message_assembly = f"Unrecognized plate pattern: {detection_sequence}"
                 final_plate_string = "Pattern Error"
                 error_occurred = True

            if not final_plate_string and not error_occurred:
                 error_occurred = True
                 error_message_assembly = "Failed to assemble plate string"

            logger.info(f">>> FINAL PLATE STRING: {final_plate_string} <<< (Confidence: {overall_confidence:.2f})")
            final_error_message = error_message_assembly if error_occurred else None
            return final_plate_string, overall_confidence, final_error_message

        except Exception as e:
            logger.error(f"Error in detection pipeline: {type(e).__name__}: {e}", exc_info=True)
            return "", 0.0, f"Internal server error during detection: {type(e).__name__}"

    # --- gRPC Handler Method ---
    def DetectPlate(self, request, context):
        """Handles the gRPC request to detect a plate."""
        start_time = time.time()
        filename = request.filename or "unknown"
        logger.info(f"Received DetectPlate request (filename: {filename})")

        plate_number, confidence, error_message = self._perform_detection(request.image)

        success = error_message is None and bool(plate_number) and "Error" not in plate_number

        end_time = time.time()
        processing_time = end_time - start_time
        logger.info(f"Request processed in {processing_time:.4f} seconds.")

        if success:
            logger.info(f"Sending SUCCESS response: Plate='{plate_number}', Confidence={confidence:.4f}")
        else:
            logger.warning(f"Sending FAILURE response: Error='{error_message or 'Assembly failed or no plate detected'}' Plate='{plate_number}'")

        return plate_detection_pb2.PlateResponse(
            success=success,
            plate_number=plate_number if plate_number else "",
            confidence=confidence,
            error_message=error_message if error_message else ""
        )

# --- Server Setup ---

def serve():
    """Start the gRPC server"""
    max_workers = int(os.getenv("GRPC_MAX_WORKERS", 10)) # Allow configuring workers via env var
    port = int(os.getenv("GRPC_PORT", 50051)) # Allow configuring port via env var

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))

    try:
        # Instantiate the servicer (this will load models)
        servicer_instance = PlateDetectionServicer()
    except Exception as init_error:
        logger.critical(f"Failed to initialize PlateDetectionServicer: {init_error}", exc_info=True)
        sys.exit("Initialization failed, cannot start server.")

    plate_detection_pb2_grpc.add_PlateDetectionServiceServicer_to_server(
        servicer_instance, server)

    listen_addr = f'[::]:{port}'
    server.add_insecure_port(listen_addr)
    server.start()
    logger.info(f"Server started successfully. Listening on {listen_addr}")

    try:
        # Keep the server running indefinitely
        while True:
            time.sleep(86400) # Sleep for a day
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Stopping server...")
        server.stop(grace=5) # Allow 5 seconds for ongoing requests
        logger.info("Server stopped gracefully.")
    except Exception as e:
        logger.critical(f"An unexpected error occurred in the server loop: {e}", exc_info=True)
        server.stop(0) # Force stop
        logger.critical("Server stopped due to unexpected error.")


if __name__ == '__main__':
    # --- FIX: Correct logger message ---
    logger.info("Starting plate detection gRPC server (Stage 1+2+OCR Approach)...")
    serve()