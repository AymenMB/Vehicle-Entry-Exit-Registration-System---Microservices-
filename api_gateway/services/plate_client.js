const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const path = require('path');
const fs = require('fs');

// Path to plate detection proto file
const PLATE_PROTO_PATH = path.resolve(__dirname, '../../detect/protos/plate_detection.proto');

// Check if proto file exists
if (!fs.existsSync(PLATE_PROTO_PATH)) {
    console.error(`Proto file not found: ${PLATE_PROTO_PATH}`);
    process.exit(1);
}

// Load proto file
const packageDefinition = protoLoader.loadSync(PLATE_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
});

// Load proto definition
const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
const plateDetection = protoDescriptor.platedetection;

// Create client
const client = new plateDetection.PlateDetectionService(
    'localhost:50051', 
    grpc.credentials.createInsecure()
);

/**
 * Detect license plate from car image
 * @param {Buffer} imageData - Image data as buffer
 * @param {string} filename - Filename of the image
 * @returns {Promise<Object>} - Plate detection results
 */
function detectPlate(imageData, filename) {
    return new Promise((resolve, reject) => {
        client.DetectPlate({
            image: imageData,
            filename: filename || 'uploaded_image.jpg'
        }, { deadline: Date.now() + 30000 }, (error, response) => {
            if (error) {
                console.error('Plate detection error:', error);
                reject(error);
            } else {
                console.log('Plate detection response:', response);
                resolve({
                    success: response.success,
                    plateNumber: response.plate_number,
                    confidence: response.confidence,
                    error: response.error_message
                });
            }
        });
    });
}

module.exports = { detectPlate };
