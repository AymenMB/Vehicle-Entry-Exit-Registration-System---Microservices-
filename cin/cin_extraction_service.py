import grpc
from concurrent import futures
import os
import sys
import numpy as np
import cv2 # OpenCV for image processing
import json
import time
import logging # For logging

# Add protos directory to sys.path
PROTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'protos')
if PROTOS_DIR not in sys.path:
    sys.path.append(PROTOS_DIR)

# Import EasyOCR and OpenVINO runtime
try:
    import easyocr
    from openvino.runtime import Core
except ImportError as e:
    logging.error(f"Missing critical dependencies: {e}. Please ensure EasyOCR and OpenVINO are installed.")
    sys.exit(1)

# Import generated gRPC modules
try:
    from protos import cin_extraction_pb2
    from protos import cin_extraction_pb2_grpc
except ImportError as e:
    logging.error(f"Error importing protobuf modules from {PROTOS_DIR}: {e}. Run generate_cin_grpc.py.")
    sys.exit(1)

# --- Configuration from run2.py (adapted) ---
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
MODEL_XML_PATH = os.path.join(MODEL_DIR, "saved_model.xml")
MODEL_BIN_PATH = os.path.join(MODEL_DIR, "saved_model.bin")

# Determine LABEL_MAP_PATH, trying model_meta first, then current dir
LABEL_MAP_PATH_PRIMARY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_meta", "dm.json")
LABEL_MAP_PATH_FALLBACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dm.json")
LABEL_MAP_PATH = ""
if os.path.exists(LABEL_MAP_PATH_PRIMARY):
    LABEL_MAP_PATH = LABEL_MAP_PATH_PRIMARY
elif os.path.exists(LABEL_MAP_PATH_FALLBACK):
    LABEL_MAP_PATH = LABEL_MAP_PATH_FALLBACK
else:
    logging.error(f"Label map (dm.json) not found in {LABEL_MAP_PATH_PRIMARY} or {LABEL_MAP_PATH_FALLBACK}")
    # Service can still start, but detection will fail if label map is crucial later

CONFIDENCE_THRESHOLD = 0.54 # Default, can be adjusted

# Preprocessing Parameters (from run2.py)
INPUT_HEIGHT = 640
INPUT_WIDTH = 640
NORM_MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float32) # R, G, B
NORM_STD = np.array([58.395, 57.12, 57.375], dtype=np.float32)  # R, G, B

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CinExtractionService")

class CinExtractionServicer(cin_extraction_pb2_grpc.CinExtractionServiceServicer):
    def __init__(self):
        logger.info("Initializing CinExtractionService...")
        self.ocr_reader = None
        self.model = None
        self.compiled_model = None
        self.class_id_to_name = {}
        self.input_layer_name = None # Store input layer name
        self.output_dets_layer_name = "dets" # Default, confirm from your model
        self.output_labels_layer_name = "labels" # Default, confirm from your model

        self._initialize_easyocr()
        self._load_label_map()
        self._initialize_openvino_model()
        logger.info("CinExtractionService initialized.")

    def _initialize_easyocr(self):
        try:
            logger.info("Initializing EasyOCR Reader (English and Arabic)... May download models on first run.")
            self.ocr_reader = easyocr.Reader(['en', 'ar'], gpu=False) # gpu=False for CPU
            logger.info("EasyOCR Reader initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing EasyOCR: {e}", exc_info=True)
            # Depending on requirements, you might want to raise an error or allow the service to run without OCR

    def _load_label_map(self):
        if not LABEL_MAP_PATH:
            logger.warning("LABEL_MAP_PATH is not set. Skipping label map loading.")
            return
        try:
            with open(LABEL_MAP_PATH, 'r') as f:
                label_map_data = json.load(f)
            # Assuming structure like: {"0": {"name": "id"}, "1": {"name": "name"}, ...}
            self.class_id_to_name = {int(k): v['name'] for k, v in label_map_data.items()}
            logger.info(f"Loaded label map with {len(self.class_id_to_name)} classes from {LABEL_MAP_PATH}.")
        except FileNotFoundError:
            logger.error(f"Label map file not found at {LABEL_MAP_PATH}. Detection might not work as expected.")
        except Exception as e:
            logger.error(f"Error loading or parsing label map from {LABEL_MAP_PATH}: {e}", exc_info=True)

    def _initialize_openvino_model(self):
        try:
            logger.info("Initializing OpenVINO Runtime Core...")
            core = Core()
            logger.info(f"Loading OpenVINO model from XML: {MODEL_XML_PATH} and BIN: {MODEL_BIN_PATH}")
            if not os.path.exists(MODEL_XML_PATH) or not os.path.exists(MODEL_BIN_PATH):
                logger.error(f"Model files not found. XML: {MODEL_XML_PATH}, BIN: {MODEL_BIN_PATH}")
                raise FileNotFoundError("OpenVINO model files missing.")
            
            self.model = core.read_model(model=MODEL_XML_PATH, weights=MODEL_BIN_PATH)
            
            # Get input and output layer names dynamically if possible, or use defaults
            self.input_layer_name = self.model.input(0).get_any_name()
            logger.info(f"Model input layer: {self.input_layer_name}")

            # Verify output layer names exist
            output_names = [out.get_any_name() for out in self.model.outputs]
            logger.info(f"Available model output layers: {output_names}")
            if self.output_dets_layer_name not in output_names:
                logger.warning(f"Output layer '{self.output_dets_layer_name}' not found in model. Using first output as fallback for dets.")
                # Fallback or error, depending on how critical these specific names are
                # For now, let's assume the order or first one might work, or it will fail at inference
            if self.output_labels_layer_name not in output_names:
                logger.warning(f"Output layer '{self.output_labels_layer_name}' not found in model. Using second output as fallback for labels if available.")

            logger.info("Compiling OpenVINO model for CPU...")
            self.compiled_model = core.compile_model(model=self.model, device_name="CPU")
            logger.info("OpenVINO model loaded and compiled successfully.")
        except Exception as e:
            logger.error(f"Error initializing OpenVINO model: {e}", exc_info=True)
            # Service might not be able to function without the model
            raise # Re-raise to prevent service from starting in a broken state

    def _preprocess_image(self, image_np, target_height, target_width, mean, std):
        """Preprocesses a NumPy image array for the model (from run2.py)."""
        original_h, original_w = image_np.shape[:2]

        scale_h = target_height / original_h
        scale_w = target_width / original_w
        scale = min(scale_h, scale_w)

        new_h, new_w = int(original_h * scale), int(original_w * scale)
        if new_h <= 0 or new_w <= 0:
            raise ValueError(f"Invalid resized dimensions ({new_w}x{new_h}) from original ({original_w}x{original_h}) with scale {scale}")
        
        resized_image = cv2.resize(image_np, (new_w, new_h))

        pad_h = target_height - new_h
        pad_w = target_width - new_w
        top, bottom = pad_h // 2, pad_h - (pad_h // 2)
        left, right = pad_w // 2, pad_w - (pad_w // 2)

        padded_image = cv2.copyMakeBorder(
            resized_image, top, bottom, left, right,
            cv2.BORDER_CONSTANT, value=(0, 0, 0) # Black padding
        )

        rgb_image = cv2.cvtColor(padded_image, cv2.COLOR_BGR2RGB)
        normalized_image = (rgb_image.astype(np.float32) - mean) / std
        chw_image = normalized_image.transpose((2, 0, 1)) # HWC to CHW
        input_tensor = np.expand_dims(chw_image, axis=0) # Add batch dimension NCHW

        return input_tensor, original_h, original_w, scale, top, left

    def ExtractCinData(self, request, context):
        logger.info(f"Received CIN extraction request for file: {request.filename}")
        response = cin_extraction_pb2.CinResponse(success=False)

        if not self.ocr_reader:
            response.error_message = "OCR reader is not initialized."
            logger.error(response.error_message)
            return response
        if not self.compiled_model:
            response.error_message = "OpenVINO model is not initialized."
            logger.error(response.error_message)
            return response
        if not self.class_id_to_name:
            logger.warning("Label map is not loaded. OCR will be performed on detected boxes but class names will be missing.")
            # Allow proceeding but with a warning, as OCR might still be useful

        try:
            # Convert image bytes to OpenCV format
            image_np_array = np.frombuffer(request.image_data, np.uint8)
            image_cv = cv2.imdecode(image_np_array, cv2.IMREAD_COLOR)
            if image_cv is None:
                response.error_message = "Failed to decode image data."
                logger.error(response.error_message)
                return response

            # 1. Preprocess image for OpenVINO model
            input_tensor, orig_h, orig_w, scale, pad_top, pad_left = self._preprocess_image(
                image_cv, INPUT_HEIGHT, INPUT_WIDTH, NORM_MEAN, NORM_STD
            )

            # 2. Run Inference with OpenVINO
            logger.info("Running OpenVINO inference...")
            infer_start_time = time.time()
            # Use dynamic input layer name found during initialization
            results = self.compiled_model.infer_new_request({self.input_layer_name: input_tensor})
            infer_time = time.time() - infer_start_time
            logger.info(f"OpenVINO inference completed in {infer_time:.4f} seconds.")

            # 3. Post-process Detections and Perform OCR (adapted from run2.py)
            # Ensure the output layer names are correct for your model
            # These might need to be fetched from `self.model.outputs` if they differ from defaults
            output_dets = results[self.compiled_model.output(self.output_dets_layer_name)] # Access by actual layer object
            output_labels = results[self.compiled_model.output(self.output_labels_layer_name)]

            # Assuming output_dets is [1, N, 5] (batch, num_detections, [x_min, y_min, x_max, y_max, confidence])
            # Assuming output_labels is [1, N] (batch, num_detections)
            detections = []
            if output_dets.shape[0] == 1 and output_labels.shape[0] == 1:
                num_detections_actual = output_dets.shape[1]
                for i in range(num_detections_actual):
                    confidence = output_dets[0, i, 4]
                    if confidence >= CONFIDENCE_THRESHOLD:
                        label_id = int(output_labels[0, i])
                        class_name = self.class_id_to_name.get(label_id, f"unknown_id_{label_id}")
                        
                        # Coordinates are for the padded/resized input (640x640)
                        x_min_pad = output_dets[0, i, 0]
                        y_min_pad = output_dets[0, i, 1]
                        x_max_pad = output_dets[0, i, 2]
                        y_max_pad = output_dets[0, i, 3]

                        # Scale back to original image coordinates
                        x_min_orig = max(0, (x_min_pad - pad_left) / scale)
                        y_min_orig = max(0, (y_min_pad - pad_top) / scale)
                        x_max_orig = min(orig_w, (x_max_pad - pad_left) / scale)
                        y_max_orig = min(orig_h, (y_max_pad - pad_top) / scale)
                        
                        detections.append({
                            'class_name': class_name,
                            'label_id': label_id,
                            'confidence': float(confidence),
                            'box_orig': [int(x_min_orig), int(y_min_orig), int(x_max_orig), int(y_max_orig)],
                            'box_padded': [int(x_min_pad), int(y_min_pad), int(x_max_pad), int(y_max_pad)]
                        })
            else:
                logger.warning(f"Unexpected output shapes. Dets: {output_dets.shape}, Labels: {output_labels.shape}")

            logger.info(f"Found {len(detections)} detections above threshold {CONFIDENCE_THRESHOLD}.")

            extracted_texts = {}
            # For storing confidences of OCR per field if needed
            ocr_confidences = {}

            for det in detections:
                field_name = det['class_name']
                x1, y1, x2, y2 = det['box_orig']

                # Ensure coordinates are valid
                if x1 >= x2 or y1 >= y2:
                    logger.warning(f"Skipping invalid box for {field_name}: {[x1,y1,x2,y2]}")
                    continue
                
                # Crop the detected region from the original image (image_cv)
                cropped_image = image_cv[y1:y2, x1:x2]

                if cropped_image.size == 0:
                    logger.warning(f"Skipping empty crop for {field_name} at box {[x1,y1,x2,y2]}.")
                    continue
                
                # Perform OCR on the cropped image
                # EasyOCR returns a list of (bbox, text, confidence_score)
                ocr_start_time = time.time()
                ocr_result_list = self.ocr_reader.readtext(cropped_image, detail=1) # detail=1 for confidence
                ocr_time = time.time() - ocr_start_time
                logger.info(f"OCR for field '{field_name}' (box: {[x1,y1,x2,y2]}) took {ocr_time:.4f}s, found {len(ocr_result_list)} results.")

                # Combine OCR results for the current field, take the one with highest confidence or combine intelligently
                current_field_text = ""
                current_field_confidence_sum = 0
                num_ocr_parts = 0
                if ocr_result_list:
                    # For simplicity, concatenating text. More sophisticated logic might be needed.
                    # Example: choose the text with the highest confidence, or filter by confidence.
                    best_text_for_field = ""
                    highest_conf_for_field = 0.0
                    for (bbox_ocr, text_ocr, conf_ocr) in ocr_result_list:
                        logger.debug(f"  OCR raw for {field_name}: '{text_ocr}' (conf: {conf_ocr:.2f})")
                        current_field_text += text_ocr + " " # Add space between parts
                        current_field_confidence_sum += conf_ocr
                        num_ocr_parts +=1
                        if conf_ocr > highest_conf_for_field:
                            highest_conf_for_field = conf_ocr
                            best_text_for_field = text_ocr # Store best single piece of text
                    
                    # Store the concatenated text and average confidence for the field
                    extracted_texts[field_name] = current_field_text.strip()
                    if num_ocr_parts > 0:
                        ocr_confidences[field_name] = current_field_confidence_sum / num_ocr_parts
                    else:
                        ocr_confidences[field_name] = 0.0
                    logger.info(f"  OCR aggregated for {field_name}: '{extracted_texts[field_name]}' (avg_conf: {ocr_confidences[field_name]:.2f})")

            # Populate response from extracted_texts and ocr_confidences
            # Map your label names (e.g., 'id', 'name', 'lastname') to proto fields
            # This mapping depends on how your `dm.json` names the classes.
            # Example mapping (adjust based on your actual class names in dm.json):
            #   'id_card_number_field_label' -> response.id_number
            #   'name_field_label' -> response.name
            #   'lastname_field_label' -> response.lastname

            # You need to know the exact class names from your dm.json
            # For example, if dm.json has: "0": {"name": "cin_id"}, "1": {"name": "cin_nom"}, "2": {"name": "cin_prenom"}
            # Then you would use these keys:
            response.id_number = extracted_texts.get("id", "") # Replace "id" with actual label name for ID
            response.name = extracted_texts.get("name", "")       # Replace "name" with actual label name for Name
            response.lastname = extracted_texts.get("lastname", "") # Replace "lastname" with actual label name for Lastname
            
            response.confidence_id = float(ocr_confidences.get("id", 0.0))
            response.confidence_name = float(ocr_confidences.get("name", 0.0))
            response.confidence_lastname = float(ocr_confidences.get("lastname", 0.0))
            
            # A more robust way if class names are not fixed or for dynamic assignment:
            # for key, text_val in extracted_texts.items():
            #     if "id" in key.lower(): # Example heuristic
            #         response.id_number = text_val
            #         response.confidence_id = float(ocr_confidences.get(key, 0.0))
            #     elif "nom" in key.lower() or "lastname" in key.lower(): # Example heuristic
            #         response.lastname = text_val
            #         response.confidence_lastname = float(ocr_confidences.get(key, 0.0))
            #     elif "prenom" in key.lower() or "name" in key.lower() and "lastname" not in key.lower(): # Example heuristic
            #         response.name = text_val
            #         response.confidence_name = float(ocr_confidences.get(key, 0.0))

            if response.id_number or response.name or response.lastname:
                response.success = True
            else:
                response.success = False # Or True if partial results are acceptable
                response.error_message = "No information could be extracted, or all fields were empty after OCR."
                if not detections:
                    response.error_message = "No relevant fields detected in the image."
            
            logger.info(f"Extraction result: Success={response.success}, ID='{response.id_number}', Name='{response.name}', Lastname='{response.lastname}'")

        except ValueError as ve:
            response.error_message = f"Image processing error: {ve}"
            logger.error(response.error_message, exc_info=True)
        except RuntimeError as rt_err: # Catch OpenVINO or other runtime errors
            response.error_message = f"Runtime error during inference: {rt_err}"
            logger.error(response.error_message, exc_info=True)
        except Exception as e:
            response.error_message = f"An unexpected error occurred: {type(e).__name__}: {e}"
            logger.error(response.error_message, exc_info=True)
        
        return response

def serve(port=50052):
    max_workers = int(os.getenv("GRPC_MAX_WORKERS_CIN", 10))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    
    try:
        servicer_instance = CinExtractionServicer() # Initialize servicer
    except Exception as e:
        logger.error(f"Failed to initialize CinExtractionServicer: {e}. Server cannot start.", exc_info=True)
        return

    cin_extraction_pb2_grpc.add_CinExtractionServiceServicer_to_server(
        servicer_instance, server
    )
    listen_addr = f'[::]:{port}'
    server.add_insecure_port(listen_addr)
    server.start()
    logger.info(f"CIN Extraction gRPC Server started. Listening on {listen_addr}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Server shutting down due to KeyboardInterrupt...")
        server.stop(0) # Graceful stop
    except Exception as e:
        logger.error(f"Server unexpectedly stopped: {e}", exc_info=True)
        server.stop(0)

if __name__ == '__main__':
    service_port = int(os.getenv("CIN_SERVICE_PORT", 50052))
    logger.info(f"Starting CIN Extraction gRPC service on port {service_port}...")
    serve(port=service_port)
