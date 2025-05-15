const { Kafka } = require('kafkajs');
const kafkaConfig = require('../../kafka_config');
const winston = require('winston');

// Configure logging
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.printf(info => `${info.timestamp} ${info.level}: ${info.message}`)
    ),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({ filename: 'kafka_producer.log' })
    ]
});

// Check if Kafka is enabled from environment variable
const kafkaEnabled = process.env.KAFKA_ENABLED !== 'false';

// Initialize Kafka client or dummy if disabled
let kafka = null;
let producer = null;
let isProducerConnected = false;

if (kafkaEnabled) {
    try {
        kafka = new Kafka({
            clientId: 'vehicle-registration-api-gateway',
            brokers: kafkaConfig.brokers
        });
        
        // Create producer
        producer = kafka.producer(kafkaConfig.producerConfig);
        
        logger.info('Kafka client initialized');
    } catch (error) {
        logger.error(`Failed to initialize Kafka client: ${error.message}`);
    }
} else {
    logger.warn('Kafka is disabled by configuration. All Kafka operations will be no-ops.');
}

/**
 * Connect to Kafka broker
 */
async function connect() {
    if (!kafkaEnabled) {
        logger.info('Kafka is disabled. Skipping connection.');
        return false;
    }
    
    try {
        if (!producer) {
            logger.error('Cannot connect to Kafka: producer not initialized');
            return false;
        }
        
        await producer.connect();
        isProducerConnected = true;
        logger.info('Connected to Kafka broker');
        return true;
    } catch (error) {
        isProducerConnected = false;
        logger.error(`Failed to connect to Kafka broker: ${error.message}`);
        return false;
    }
}

/**
 * Disconnect from Kafka broker
 */
async function disconnect() {
    if (!kafkaEnabled || !producer) {
        return true;
    }
    
    try {
        await producer.disconnect();
        isProducerConnected = false;
        logger.info('Disconnected from Kafka broker');
        return true;
    } catch (error) {
        logger.error(`Failed to disconnect from Kafka broker: ${error.message}`);
        return false;
    }
}

/**
 * Send registration event to Kafka
 * @param {Object} registration Registration data
 * @returns {Promise<boolean>} Success status
 */
async function sendRegistrationEvent(registration) {
    if (!kafkaEnabled || !producer) {
        logger.info('Kafka is disabled. Registration event not sent.');
        return false;
    }
    
    try {
        // Ensure we have a producer connection
        if (!isProducerConnected) {
            try {
                await connect();
            } catch (connError) {
                logger.error(`Failed to reconnect to Kafka: ${connError.message}`);
                return false;
            }
        }
        
        // If still not connected, return false
        if (!isProducerConnected) {
            logger.error('Cannot send registration event: Kafka is not connected');
            return false;
        }
        
        // Define the message payload
        const message = {
            key: registration.registrationId,
            value: JSON.stringify({
                ...registration,
                timestamp: registration.timestamp || new Date().toISOString(),
                kafkaTimestamp: new Date().toISOString()
            })
        };
        
        // Send the message to the registrations topic
        await producer.send({
            topic: kafkaConfig.topics.registrations,
            messages: [message]
        });
        
        logger.info(`Registration event sent to Kafka: ${registration.registrationId}`);
        return true;
    } catch (error) {
        logger.error(`Failed to send registration event to Kafka: ${error.message}`);
        
        // Try to send error notification to error topic if connected
        if (isProducerConnected) {
            try {
                await producer.send({
                    topic: kafkaConfig.topics.errors,
                    messages: [{
                        value: JSON.stringify({
                            error: error.message,
                            source: 'api_gateway',
                            service: 'kafka_producer',
                            timestamp: new Date().toISOString(),
                            details: {
                                registrationId: registration.registrationId,
                                type: registration.type
                            }
                        })
                    }]
                });
            } catch (nestedError) {
                logger.error(`Failed to send error notification: ${nestedError.message}`);
            }
        }
        
        return false;
    }
}

/**
 * Send system notification event to Kafka
 * @param {string} message Notification message
 * @param {string} level Notification level (info, warning, error)
 * @param {Object} metadata Additional metadata
 * @returns {Promise<boolean>} Success status
 */
async function sendNotification(message, level = 'info', metadata = {}) {
    if (!kafkaEnabled || !producer) {
        logger.info(`Kafka is disabled. Notification not sent: ${message}`);
        return false;
    }
    
    try {
        // Ensure we have a producer connection
        if (!isProducerConnected) {
            try {
                await connect();
            } catch (connError) {
                logger.error(`Failed to reconnect to Kafka: ${connError.message}`);
                return false;
            }
        }
        
        // If still not connected, return false
        if (!isProducerConnected) {
            logger.error('Cannot send notification: Kafka is not connected');
            return false;
        }
        
        // Send notification to the notifications topic
        await producer.send({
            topic: kafkaConfig.topics.notifications,
            messages: [{
                value: JSON.stringify({
                    message,
                    level,
                    timestamp: new Date().toISOString(),
                    metadata
                })
            }]
        });
        
        logger.info(`Notification sent to Kafka: ${message}`);
        return true;
    } catch (error) {
        logger.error(`Failed to send notification to Kafka: ${error.message}`);
        return false;
    }
}

/**
 * Check if Kafka is enabled
 * @returns {boolean} Kafka enabled status
 */
function isKafkaEnabled() {
    return kafkaEnabled;
}

// Export functions
module.exports = {
    connect,
    disconnect,
    sendRegistrationEvent,
    sendNotification,
    isKafkaEnabled
};
