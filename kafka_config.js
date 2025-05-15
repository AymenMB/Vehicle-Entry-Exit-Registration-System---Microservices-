/**
 * Kafka configuration for Vehicle Registration System
 */

// Determine if we should use Docker or local Kafka
const useDockerKafka = process.env.KAFKA_DOCKER === 'true';

// Default broker settings based on installation type
const defaultBrokers = useDockerKafka 
    ? ['localhost:9093']  
    : ['localhost:9092']; 

module.exports = {
    
    brokers: process.env.KAFKA_BROKERS 
        ? process.env.KAFKA_BROKERS.split(',') 
        : defaultBrokers,
    
    // Topic definitions
    topics: {
        registrations: process.env.KAFKA_TOPIC_REGISTRATIONS || 'vehicle-registrations',
        notifications: process.env.KAFKA_TOPIC_NOTIFICATIONS || 'system-notifications',
        errors: process.env.KAFKA_TOPIC_ERRORS || 'system-errors'
    },
    
    // Consumer group IDs
    consumerGroups: {
        registrationProcessor: 'registration-processor-group',
        notificationService: 'notification-service-group'
    },
    
    // Producer configuration
    producerConfig: {
        allowAutoTopicCreation: true,
        transactionTimeout: 30000
    },
    
    // Consumer configuration
    consumerConfig: {
        sessionTimeout: 30000,
        heartbeatInterval: 3000,
        metadataMaxAge: 180000,
        autoCommit: true,
        autoCommitInterval: 5000
    },
    
    // Additional configuration for connection retries
    connectionRetry: {
        initialRetryTime: 1000,
        retries: 5
    },
    
    // Default Kafka home directory for local installations
    kafkaHome: process.env.KAFKA_HOME || 'C:\\kafka'
};
