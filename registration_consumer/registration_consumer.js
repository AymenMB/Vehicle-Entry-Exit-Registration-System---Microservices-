const { Kafka } = require('kafkajs');
const fs = require('fs');
const path = require('path');
const winston = require('winston');
const mongoose = require('mongoose');
const kafkaConfig = require('../kafka_config');
const connectDB = require('./config/db');
const Registration = require('./models/Registration');
const dotenv = require('dotenv');

// Load environment variables
dotenv.config();

// Configure logging
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.printf(info => `${info.timestamp} ${info.level}: ${info.message}`)
    ),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({ filename: 'registration_consumer.log' })
    ]
});

// Initialize Kafka client
const kafka = new Kafka({
    clientId: 'vehicle-registration-consumer',
    brokers: kafkaConfig.brokers
});

// Create consumer
const consumer = kafka.consumer({ 
    groupId: kafkaConfig.consumerGroups.registrationProcessor
});

/**
 * Get stats from MongoDB
 * @returns {Promise<Object>} Promise resolving to statistics object
 */
async function getStats() {
    try {
        // Use MongoDB aggregation to get stats
        const entriesCount = await Registration.countDocuments({ type: 'entry' });
        const exitsCount = await Registration.countDocuments({ type: 'exit' });
        
        // Get latest timestamp
        const latestRecord = await Registration.findOne().sort({ timestamp: -1 });
        const lastUpdated = latestRecord ? latestRecord.timestamp : new Date().toISOString();
        
        return {
            totalEntries: entriesCount,
            totalExits: exitsCount,
            lastUpdated: lastUpdated
        };
    } catch (error) {
        logger.error(`Failed to get stats from MongoDB: ${error.message}`);
        return {
            totalEntries: 0,
            totalExits: 0,
            lastUpdated: new Date().toISOString()
        };
    }
}

/**
 * Get unique vehicles and persons count
 * @returns {Promise<Object>} Promise resolving to unique counts
 */
async function getUniqueCounts() {
    try {
        // Count unique plate numbers
        const uniqueVehicles = await Registration.distinct('plateData.plateNumber');
        const uniqueVehiclesCount = uniqueVehicles.filter(Boolean).length;
        
        // Count unique ID numbers
        const uniquePersons = await Registration.distinct('cinData.idNumber');
        const uniquePersonsCount = uniquePersons.filter(Boolean).length;
        
        return {
            vehicles: uniqueVehiclesCount,
            persons: uniquePersonsCount
        };
    } catch (error) {
        logger.error(`Failed to get unique counts from MongoDB: ${error.message}`);
        return { vehicles: 0, persons: 0 };
    }
}

/**
 * Process a registration event
 * @param {Object} registration Registration data
 */
async function processRegistration(registration) {
    try {
        // Add timestamp if not present
        if (!registration.timestamp) {
            registration.timestamp = new Date().toISOString();
        }
        
        // Create a new registration document in MongoDB
        const newRegistration = new Registration(registration);
        await newRegistration.save();
        
        logger.info(`Registration processed and saved to MongoDB: ${registration.registrationId} (${registration.type})`);
        
        // Get updated stats
        const stats = await getStats();
        const uniqueCounts = await getUniqueCounts();
        
        logger.info(`Stats: ${stats.totalEntries} entries, ${stats.totalExits} exits`);
        logger.info(`Unique vehicles: ${uniqueCounts.vehicles}, Unique persons: ${uniqueCounts.persons}`);
    } catch (error) {
        logger.error(`Failed to process registration: ${error.message}`);
    }
}

/**
 * Connect to Kafka and start consuming messages
 */
async function run() {
    try {
        // Connect to MongoDB first
        await connectDB();
        logger.info('Connected to MongoDB database');
        
        // Connect to Kafka
        await consumer.connect();
        logger.info('Connected to Kafka broker');
        
        // Subscribe to registrations topic
        await consumer.subscribe({ 
            topic: kafkaConfig.topics.registrations, 
            fromBeginning: false 
        });
        logger.info(`Subscribed to topic: ${kafkaConfig.topics.registrations}`);
        
        // Start consuming messages
        await consumer.run({
            eachMessage: async ({ topic, partition, message }) => {
                try {
                    // Parse message value
                    const registration = JSON.parse(message.value.toString());
                    logger.info(`Received registration event: ${registration.registrationId}`);
                    
                    // Process the registration
                    await processRegistration(registration);
                } catch (error) {
                    logger.error(`Error processing message: ${error.message}`);
                }
            }
        });
    } catch (error) {
        logger.error(`Consumer error: ${error.message}`);
        process.exit(1);
    }
}

// Handle process termination
process.on('SIGINT', async () => {
    try {
        logger.info('Disconnecting consumer...');
        await consumer.disconnect();
        logger.info('Consumer disconnected');
        
        // Close MongoDB connection
        logger.info('Closing MongoDB connection...');
        await mongoose.connection.close();
        logger.info('MongoDB connection closed');
        
        process.exit(0);
    } catch (error) {
        logger.error(`Error during shutdown: ${error.message}`);
        process.exit(1);
    }
});

// Start the consumer
logger.info('Starting Kafka consumer for vehicle registrations');
run().catch(error => {
    logger.error(`Failed to start consumer: ${error.message}`);
});
