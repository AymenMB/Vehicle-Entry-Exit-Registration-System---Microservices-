const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const path = require('path');
const fs = require('fs');

// Get the aggregator port from port file or environment variable with proper fallbacks
function getAggregatorPort() {
    // First check if we have a port file from the aggregator
    const portFilePath = path.join(__dirname, '../../aggregator/aggregator_port.txt');
    
    try {
        if (fs.existsSync(portFilePath)) {
            const port = fs.readFileSync(portFilePath, 'utf8').trim();
            console.log(`Using aggregator port from file: ${port}`);
            return port;
        }
    } catch (error) {
        console.warn(`Could not read port file: ${error.message}`);
    }
    
    // Next check environment variable
    if (process.env.AGGREGATOR_PORT) {
        console.log(`Using aggregator port from environment: ${process.env.AGGREGATOR_PORT}`);
        return process.env.AGGREGATOR_PORT;
    }
    
    // Default port with fallbacks
    console.log('Using default aggregator port: 50050');
    return 50050;
}

// Load proto file
const PROTO_PATH = path.join(__dirname, '../../aggregator/protos/aggregator.proto');
const aggregatorPort = getAggregatorPort();
const aggregatorHost = process.env.AGGREGATOR_HOST || 'localhost';
const aggregatorAddress = `${aggregatorHost}:${aggregatorPort}`;

console.log(`Connecting to aggregator at: ${aggregatorAddress}`);

// Check if proto file exists
if (!fs.existsSync(PROTO_PATH)) {
    console.error(`Proto file not found: ${PROTO_PATH}`);
    // Better handling for missing proto file - we'll create mock implementations
    module.exports = {
        registerEntry: async () => ({ success: false, error: 'Aggregator proto file not found' }),
        registerExit: async () => ({ success: false, error: 'Aggregator proto file not found' }),
        healthCheck: async () => ({ status: 'error', error: 'Aggregator proto file not found' })
    };
} else {
    const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
        keepCase: true,
        longs: String,
        enums: String,
        defaults: true,
        oneofs: true
    });

    const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
    const AggregatorService = protoDescriptor.aggregator.AggregatorService;

    // Create a client with deadline of 30 seconds
    const client = new AggregatorService(
        aggregatorAddress,
        grpc.credentials.createInsecure(),
        {
            'grpc.keepalive_time_ms': 10000,
            'grpc.keepalive_timeout_ms': 5000,
            'grpc.keepalive_permit_without_calls': 1,
            'grpc.http2.max_pings_without_data': 0,
            'grpc.http2.min_time_between_pings_ms': 10000,
            'grpc.http2.min_ping_interval_without_data_ms': 5000
        }
    );

    /**
     * Register vehicle entry
     * @param {Buffer} cinImageBuffer CIN image buffer
     * @param {string} cinFilename CIN image filename
     * @param {Buffer} vehicleImageBuffer Vehicle image buffer
     * @param {string} vehicleFilename Vehicle image filename
     * @returns {Promise<Object>} Registration result
     */
    async function registerEntry(cinImageBuffer, cinFilename, vehicleImageBuffer, vehicleFilename) {
        return new Promise((resolve, reject) => {
            client.RegisterEntry({
                cin_image: cinImageBuffer,
                cin_filename: cinFilename,
                vehicle_image: vehicleImageBuffer,
                vehicle_filename: vehicleFilename
            }, { deadline: Date.now() + 30000 }, (err, response) => {
                if (err) {
                    console.error('Error in registerEntry:', err);
                    reject(err);
                } else {
                    resolve({
                        success: true,
                        cinData: {
                            idNumber: response.cin_data?.id_number,
                            name: response.cin_data?.name,
                            lastname: response.cin_data?.lastname,
                            confidenceId: response.cin_data?.confidence_id,
                            confidenceName: response.cin_data?.confidence_name,
                            confidenceLastname: response.cin_data?.confidence_lastname
                        },
                        plateData: {
                            plateNumber: response.plate_data?.plate_number,
                            confidence: response.plate_data?.confidence
                        },
                        registrationId: response.registration_id,
                        timestamp: response.timestamp,
                        type: response.type
                    });
                }
            });
        });
    }

    /**
     * Register vehicle exit
     * @param {Buffer} cinImageBuffer CIN image buffer
     * @param {string} cinFilename CIN image filename
     * @param {Buffer} vehicleImageBuffer Vehicle image buffer
     * @param {string} vehicleFilename Vehicle image filename
     * @returns {Promise<Object>} Registration result
     */
    async function registerExit(cinImageBuffer, cinFilename, vehicleImageBuffer, vehicleFilename) {
        return new Promise((resolve, reject) => {
            client.RegisterExit({
                cin_image: cinImageBuffer,
                cin_filename: cinFilename,
                vehicle_image: vehicleImageBuffer,
                vehicle_filename: vehicleFilename
            }, { deadline: Date.now() + 30000 }, (err, response) => {
                if (err) {
                    console.error('Error in registerExit:', err);
                    reject(err);
                } else {
                    resolve({
                        success: true,
                        cinData: {
                            idNumber: response.cin_data?.id_number,
                            name: response.cin_data?.name,
                            lastname: response.cin_data?.lastname,
                            confidenceId: response.cin_data?.confidence_id,
                            confidenceName: response.cin_data?.confidence_name,
                            confidenceLastname: response.cin_data?.confidence_lastname
                        },
                        plateData: {
                            plateNumber: response.plate_data?.plate_number,
                            confidence: response.plate_data?.confidence
                        },
                        registrationId: response.registration_id,
                        timestamp: response.timestamp,
                        type: response.type
                    });
                }
            });
        });
    }

    /**
     * Health check
     * @returns {Promise<Object>} Health status
     */
    async function healthCheck() {
        return new Promise((resolve, reject) => {
            client.HealthCheck({}, { deadline: Date.now() + 10000 }, (err, response) => {
                if (err) {
                    console.error('Error in healthCheck:', err);
                    resolve({
                        status: 'error',
                        cinService: 'unknown',
                        plateService: 'unknown',
                        error: err.message
                    });
                } else {
                    resolve({
                        status: response.status,
                        cinService: response.cin_service,
                        plateService: response.plate_service,
                        error: response.error
                    });
                }
            });
        });
    }

    module.exports = {
        registerEntry,
        registerExit,
        healthCheck
    };
}
