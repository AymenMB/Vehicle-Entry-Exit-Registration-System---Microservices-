const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const path = require('path');
const fs = require('fs');
const winston = require('winston');
const { v4: uuidv4 } = require('uuid');
const { processRegistration } = require('./app');

// Configure logging
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.printf(info => `${info.timestamp} ${info.level}: ${info.message}`)
    ),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({ filename: 'aggregator_service.log' })
    ]
});

// Load proto file
const PROTO_PATH = path.resolve(__dirname, './protos/aggregator.proto');

// Check if proto file exists
if (!fs.existsSync(PROTO_PATH)) {
    logger.error(`Proto file not found: ${PROTO_PATH}`);
    process.exit(1);
}

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
});

const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
const aggregatorProto = protoDescriptor.aggregator;

/**
 * Implementation of the Aggregator service
 */
const serviceImplementation = {
    // Handle vehicle entry registration
    RegisterEntry: async (call, callback) => {
        try {
            logger.info('Received RegisterEntry request');
            
            const { cin_image, cin_filename, vehicle_image, vehicle_filename } = call.request;
            
            if (!cin_image || !vehicle_image) {
                logger.error('Missing required images in RegisterEntry request');
                return callback({
                    code: grpc.status.INVALID_ARGUMENT,
                    message: 'Both CIN image and vehicle image are required'
                });
            }
            
            // Process registration
            const result = await processRegistration(
                cin_image, 
                cin_filename || 'cin_image.jpg', 
                vehicle_image, 
                vehicle_filename || 'vehicle_image.jpg',
                'entry'
            );
            
            // Generate a unique ID for this registration
            result.registration_id = uuidv4();
            result.timestamp = new Date().toISOString();
            result.type = 'entry';
            
            logger.info(`Registration entry completed: ${result.registration_id}`);
            callback(null, result);
        } catch (error) {
            logger.error('Error in RegisterEntry:', error);
            callback({
                code: grpc.status.INTERNAL,
                message: `Registration failed: ${error.message || error}`
            });
        }
    },
    
    // Handle vehicle exit registration
    RegisterExit: async (call, callback) => {
        try {
            logger.info('Received RegisterExit request');
            
            const { cin_image, cin_filename, vehicle_image, vehicle_filename } = call.request;
            
            if (!cin_image || !vehicle_image) {
                logger.error('Missing required images in RegisterExit request');
                return callback({
                    code: grpc.status.INVALID_ARGUMENT,
                    message: 'Both CIN image and vehicle image are required'
                });
            }
            
            // Process registration
            const result = await processRegistration(
                cin_image, 
                cin_filename || 'cin_image.jpg', 
                vehicle_image, 
                vehicle_filename || 'vehicle_image.jpg',
                'exit'
            );
            
            // Generate a unique ID for this registration
            result.registration_id = uuidv4();
            result.timestamp = new Date().toISOString();
            result.type = 'exit';
            
            logger.info(`Registration exit completed: ${result.registration_id}`);
            callback(null, result);
        } catch (error) {
            logger.error('Error in RegisterExit:', error);
            callback({
                code: grpc.status.INTERNAL,
                message: `Registration failed: ${error.message || error}`
            });
        }
    },
    
    // Health check endpoint
    HealthCheck: async (call, callback) => {
        try {
            logger.info('Health check requested');
            
            // ToDo: Add actual health checks for the CIN and Plate services
            callback(null, {
                status: 'ok',
                cin_service: 'connected',
                plate_service: 'connected',
                error: null
            });
        } catch (error) {
            logger.error('Error in HealthCheck:', error);
            callback(null, {
                status: 'error',
                cin_service: 'unknown',
                plate_service: 'unknown',
                error: error.message || 'Unknown error'
            });
        }
    }
};

/**
 * Start the gRPC server
 */
function startServer() {
    const server = new grpc.Server();
    server.addService(aggregatorProto.AggregatorService.service, serviceImplementation);
    
    // Try different ports if the main one is in use
    const tryPorts = [50050, 50053, 50055, 50057, 50059];
    let currentPortIndex = 0;
    
    function tryBindPort() {
        if (currentPortIndex >= tryPorts.length) {
            logger.error("Failed to bind to any available port. Exiting.");
            process.exit(1);
            return;
        }
        
        const port = tryPorts[currentPortIndex];
        logger.info(`Attempting to bind to port ${port}...`);
        
        server.bindAsync(`0.0.0.0:${port}`, grpc.ServerCredentials.createInsecure(), (err, boundPort) => {
            if (err) {
                logger.warn(`Failed to bind to port ${port}: ${err.message}`);
                currentPortIndex++;
                tryBindPort(); // Try the next port
                return;
            }
            
            // Successfully bound to a port
            logger.info(`Aggregator gRPC server started on port ${boundPort}`);
            
            // Create a port file so other services know which port we're using
            const portFilePath = path.join(__dirname, 'aggregator_port.txt');
            fs.writeFileSync(portFilePath, boundPort.toString(), 'utf8');
            logger.info(`Port information saved to ${portFilePath}`);
            
            server.start();
        });
    }
    
    // Start trying ports
    tryBindPort();
}

// Export for testing and the start function
module.exports = {
    startServer
};

// Handle graceful shutdown
process.on('SIGINT', () => {
    logger.info('Received SIGINT. Shutting down gracefully...');
    process.exit(0);
});

// Start server if this file is run directly
if (require.main === module) {
    startServer();
}
