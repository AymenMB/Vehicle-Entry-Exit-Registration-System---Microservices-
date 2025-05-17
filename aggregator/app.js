const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const path = require('path');
const fs = require('fs');
const winston = require('winston');
const util = require('util');

// Configure logging
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.printf(info => `${info.timestamp} ${info.level}: ${info.message}`)
    ),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({ filename: 'aggregator.log' })
    ]
});

// Define paths to proto files
const CIN_PROTO_PATH = path.resolve(__dirname, '../cin/protos/cin_extraction.proto');
const PLATE_PROTO_PATH = path.resolve(__dirname, '../detect/protos/plate_detection.proto');

// Check if proto files exist
if (!fs.existsSync(CIN_PROTO_PATH)) {
    logger.error(`CIN proto file not found: ${CIN_PROTO_PATH}`);
    process.exit(1);
}

if (!fs.existsSync(PLATE_PROTO_PATH)) {
    logger.error(`Plate detection proto file not found: ${PLATE_PROTO_PATH}`);
    process.exit(1);
}

// Create gRPC clients for both services
let cinClient = null;
let plateClient = null;

// Load CIN extraction service
const cinPackageDefinition = protoLoader.loadSync(CIN_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
});

const cinProto = grpc.loadPackageDefinition(cinPackageDefinition).cinextraction;
cinClient = new cinProto.CinExtractionService(
    'localhost:50052', 
    grpc.credentials.createInsecure()
);

// Load plate detection service
const platePackageDefinition = protoLoader.loadSync(PLATE_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
});

const plateProto = grpc.loadPackageDefinition(platePackageDefinition).platedetection;
plateClient = new plateProto.PlateDetectionService(
    'localhost:50051', 
    grpc.credentials.createInsecure()
);

// Create promisified versions of gRPC client methods
const extractCinData = util.promisify(cinClient.ExtractCinData).bind(cinClient);
const detectPlate = util.promisify(plateClient.DetectPlate).bind(plateClient);

/**
 * Process vehicle entry or exit
 * @param {Buffer} cinImageBuffer - CIN image buffer
 * @param {string} cinFilename - CIN image filename
 * @param {Buffer} vehicleImageBuffer - Vehicle image buffer
 * @param {string} vehicleFilename - Vehicle image filename
 * @param {string} type - 'entry' or 'exit'
 * @returns {Promise<Object>} - Registration result
 */
async function processRegistration(cinImageBuffer, cinFilename, vehicleImageBuffer, vehicleFilename, type) {
    logger.info(`Processing ${type} registration`);
    
    try {
        if (!cinImageBuffer || !vehicleImageBuffer) {
            logger.error('Missing required image data');
            return {
                success: false,
                error: 'Both CIN image and vehicle image data are required',
                cin_data: null,
                plate_data: null
            };
        }
        
        // Call both services in parallel with proper error handling
        let cinResponse, plateResponse;
        
        try {
            [cinResponse, plateResponse] = await Promise.all([
                extractCinData({
                    image_data: cinImageBuffer,
                    filename: cinFilename
                }),
                detectPlate({
                    image: vehicleImageBuffer,
                    filename: vehicleFilename
                })
            ]);
        } catch (serviceError) {
            logger.error(`Error calling microservices: ${serviceError.message}`);
            return {
                success: false,
                error: `Service communication error: ${serviceError.message}`,
                cin_data: null,
                plate_data: null
            };
        }
          logger.info(`CIN extraction result: ${JSON.stringify(cinResponse)}`);
        logger.info(`Plate detection result: ${JSON.stringify(plateResponse)}`);
          // Process and combine results
        const registrationId = `${type.toUpperCase()}-${Date.now()}`;
        const timestamp = new Date().toISOString();
        
        // Enhanced debugging for CIN response
        logger.info('CIN EXTRACTION DETAILS:');
        logger.info(`- success: ${cinResponse.success}`);
        logger.info(`- id_number: "${cinResponse.id_number || 'none'}"`);
        logger.info(`- name: "${cinResponse.name || 'none'}"`);
        logger.info(`- lastname: "${cinResponse.lastname || 'none'}"`);
        logger.info(`- error_message: "${cinResponse.error_message || 'none'}"`);
        
        // Enhanced debugging for plate response
        logger.info('PLATE DETECTION DETAILS:');
        logger.info(`- success: ${plateResponse.success}`);
        logger.info(`- plate_number: "${plateResponse.plate_number || 'none'}"`);
        logger.info(`- confidence: ${plateResponse.confidence || 0}`);
        logger.info(`- error_message: "${plateResponse.error_message || 'none'}"`);        // Extract and format the data correctly
        const firstName = cinResponse.name || "";
        const lastName = cinResponse.lastname || "";
        const fullName = `${firstName} ${lastName}`;
        
        const cleanedCinData = {
            id_number: cinResponse.id_number || "",
            name: firstName,
            lastname: lastName,
            fullName: fullName, // Added full name with space
            confidence_id: parseFloat(cinResponse.confidence_id || 0.0),
            confidence_name: parseFloat(cinResponse.confidence_name || 0.0),
            confidence_lastname: parseFloat(cinResponse.confidence_lastname || 0.0),
            error: cinResponse.error_message || ""
        };
        
        const cleanedPlateData = {
            plate_number: plateResponse.plate_number || "",
            confidence: parseFloat(plateResponse.confidence || 0.0),
            error: plateResponse.error_message || ""
        };
        
        logger.info(`Formatted CIN data: ${JSON.stringify(cleanedCinData)}`);
        logger.info(`Formatted Plate data: ${JSON.stringify(cleanedPlateData)}`);
        
        return {
            success: (cinResponse.success || cleanedCinData.id_number || cleanedCinData.name || cleanedCinData.lastname) && 
                    (plateResponse.success || cleanedPlateData.plate_number),
            cin_data: cleanedCinData,
            plate_data: cleanedPlateData,
            registration_id: registrationId,
            timestamp,
            type
        };
    } catch (error) {
        logger.error(`Error processing ${type} registration: ${error.message}`);
        return {
            success: false,
            error: `Registration failed: ${error.message}`,
            type
        };
    }
}

// Aggregator service wrapper functions
const cinExtraction = {
    extractCinData: async (cinImageBuffer, filename) => {
        try {
            logger.info(`Processing CIN extraction for ${filename}`);
            const response = await extractCinData({
                image_data: cinImageBuffer,
                filename
            });
            
            return {
                success: response.success,
                idNumber: response.id_number,
                name: response.name,
                lastname: response.lastname,
                confidenceId: response.confidence_id,
                confidenceName: response.confidence_name,
                confidenceLastname: response.confidence_lastname,
                error: response.error_message
            };
        } catch (error) {
            logger.error(`CIN extraction error: ${error.message}`);
            return {
                success: false,
                error: `CIN extraction failed: ${error.message}`
            };
        }
    }
};

const plateDetection = {
    detectPlate: async (vehicleImageBuffer, filename) => {
        try {
            logger.info(`Processing plate detection for ${filename}`);
            const response = await detectPlate({
                image: vehicleImageBuffer,
                filename
            });
            
            return {
                success: response.success,
                plateNumber: response.plate_number,
                confidence: response.confidence,
                error: response.error_message
            };
        } catch (error) {
            logger.error(`Plate detection error: ${error.message}`);
            return {
                success: false,
                error: `Plate detection failed: ${error.message}`
            };
        }
    }
};

const registration = {
    registerEntry: async (cinImageBuffer, cinFilename, vehicleImageBuffer, vehicleFilename) => {
        return processRegistration(cinImageBuffer, cinFilename, vehicleImageBuffer, vehicleFilename, 'entry');
    },
    
    registerExit: async (cinImageBuffer, cinFilename, vehicleImageBuffer, vehicleFilename) => {
        return processRegistration(cinImageBuffer, cinFilename, vehicleImageBuffer, vehicleFilename, 'exit');
    }
};

// Health check function
async function healthCheck() {
    try {
        // Check connection to both services
        await Promise.all([
            extractCinData({ image_data: Buffer.from('test'), filename: 'test.jpg' })
                .catch(err => {
                    logger.error(`CIN service health check failed: ${err.message}`);
                    throw new Error(`CIN service unavailable: ${err.message}`);
                }),
            detectPlate({ image: Buffer.from('test'), filename: 'test.jpg' })
                .catch(err => {
                    logger.error(`Plate detection service health check failed: ${err.message}`);
                    throw new Error(`Plate detection service unavailable: ${err.message}`);
                })
        ]);
        
        return {
            status: 'healthy',
            cinService: 'connected',
            plateService: 'connected'
        };
    } catch (error) {
        logger.error(`Health check failed: ${error.message}`);
        return {
            status: 'unhealthy',
            error: error.message
        };
    }
}

// Export all functions
module.exports = {
    cinExtraction,
    plateDetection,
    registration,
    healthCheck,
    processRegistration
};

// Log service startup
logger.info('Aggregator service initialized and ready to process requests');
