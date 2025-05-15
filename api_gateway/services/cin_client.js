const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const path = require('path');
const fs = require('fs');

// Path to CIN extraction proto file
const CIN_PROTO_PATH = path.resolve(__dirname, '../../cin/protos/cin_extraction.proto');

// Check if proto file exists
if (!fs.existsSync(CIN_PROTO_PATH)) {
    console.error(`Proto file not found: ${CIN_PROTO_PATH}`);
    process.exit(1);
}

// Load proto file
const packageDefinition = protoLoader.loadSync(CIN_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
});

// Load proto definition
const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
const cinExtraction = protoDescriptor.cinextraction;

// Create client
const client = new cinExtraction.CinExtractionService(
    'localhost:50052', 
    grpc.credentials.createInsecure()
);

/**
 * Extract data from CIN image
 * @param {Buffer} imageData - Image data as buffer
 * @param {string} filename - Filename of the image
 * @returns {Promise<Object>} - CIN data extraction results
 */
function extractCinData(imageData, filename) {
    return new Promise((resolve, reject) => {
        client.ExtractCinData({
            image_data: imageData,
            filename: filename || 'uploaded_image.jpg'
        }, { deadline: Date.now() + 60000 }, (error, response) => {
            if (error) {
                console.error('CIN extraction error:', error);
                reject(error);
            } else {
                console.log('CIN extraction response:', response);
                resolve({
                    success: response.success,
                    idNumber: response.id_number,
                    name: response.name,
                    lastname: response.lastname,
                    confidenceId: response.confidence_id,
                    confidenceName: response.confidence_name,
                    confidenceLastname: response.confidence_lastname,
                    error: response.error_message
                });
            }
        });
    });
}

module.exports = { extractCinData };
