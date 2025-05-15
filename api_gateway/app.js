const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
const helmet = require('helmet');
const { ApolloServer } = require('apollo-server-express');
const { graphqlUploadExpress } = require('graphql-upload');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const mongoose = require('mongoose');
const dotenv = require('dotenv');
const kafkaProducer = require('./services/kafka_producer');
const connectDB = require('./config/db');

// Load environment variables
dotenv.config();

const restRoutes = require('./routes/rest_routes');
const { typeDefs, resolvers } = require('./graphql/schema');


const app = express();
const PORT = process.env.PORT || 3000;
const upload = multer({ dest: 'uploads/' });

// Middleware
app.use(cors());
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            scriptSrc: ["'self'", "'unsafe-inline'", "cdn.jsdelivr.net"],
            styleSrc: ["'self'", "'unsafe-inline'", "cdn.jsdelivr.net"],
            imgSrc: ["'self'", "data:"],
            connectSrc: ["'self'"],
        }
    }
}));
app.use(morgan('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Ensure uploads directory exists
const uploadsDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsDir)) {
    fs.mkdirSync(uploadsDir, { recursive: true });
}

// Serve static files from 'public' directory
app.use(express.static(path.join(__dirname, 'public')));

// REST API Routes first (to avoid conflict with GraphQL middleware)
app.use('/api', restRoutes);

// Configure graphql-upload middleware only for the GraphQL endpoint
app.use('/graphql', graphqlUploadExpress({ 
    maxFileSize: 10000000, 
    maxFiles: 10,
    maxFieldSize: 10000000 
}));

// Health check endpoint
app.get('/health', (req, res) => {
    res.status(200).json({ status: 'OK', message: 'API Gateway is running' });
});

// Error handling middleware
app.use((err, req, res, next) => {
    console.error(err.stack);
    res.status(500).json({
        error: 'Internal Server Error',
        message: err.message
    });
});

// Initialize Kafka connection if enabled
if (process.env.KAFKA_ENABLED !== 'false') {
    kafkaProducer.connect()
        .then(connected => {
            if (connected) {
                console.log('Successfully connected to Kafka');
                
                // Send system startup notification
                kafkaProducer.sendNotification(
                    'API Gateway started successfully',
                    'info',
                    { timestamp: new Date().toISOString() }
                );
            } else {
                console.warn('Failed to connect to Kafka - some features will be disabled');
            }
        })
        .catch(err => {
            console.error('Error connecting to Kafka:', err.message);
        });
} else {
    console.warn('Kafka is disabled by configuration');
}

// Add this to the shutdown handler:
process.on('SIGINT', async () => {
    console.log('Shutting down API Gateway...');
    
    // Disconnect from Kafka if connected
    if (process.env.KAFKA_ENABLED !== 'false') {
        try {
            await kafkaProducer.disconnect();
            console.log('Disconnected from Kafka');
        } catch (err) {
            console.error('Error disconnecting from Kafka:', err.message);
        }
    }
    
    // Disconnect from MongoDB
    try {
        await mongoose.connection.close();
        console.log('Disconnected from MongoDB');
    } catch (err) {
        console.error('Error disconnecting from MongoDB:', err);
    }
    
    process.exit(0);
});

// Setup Apollo GraphQL Server
async function startApolloServer() {
    const server = new ApolloServer({
        typeDefs,
        resolvers,
        context: ({ req }) => ({ req })
    });

    await server.start();
    server.applyMiddleware({ app, path: '/graphql' });
    console.log(`GraphQL endpoint available at http://localhost:${PORT}${server.graphqlPath}`);
}

// Start server
async function startServer() {
    try {
        // Connect to MongoDB
        await connectDB();
        console.log('MongoDB connection established');
        
        await startApolloServer();
        app.listen(PORT, () => {
            console.log(`API Gateway running on http://localhost:${PORT}`);
            console.log(`REST API available at http://localhost:${PORT}/api`);
        });
    } catch (error) {
        console.error('Failed to start server:', error);
        process.exit(1);
    }
}

startServer();
