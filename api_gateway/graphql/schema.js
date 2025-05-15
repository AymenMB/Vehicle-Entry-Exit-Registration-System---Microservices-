const { gql } = require('apollo-server-express');
const { GraphQLUpload } = require('graphql-upload');
const fs = require('fs');
const path = require('path');
const cinClient = require('../services/cin_client');
const plateClient = require('../services/plate_client');
const aggregatorClient = require('../services/aggregator_client');

// GraphQL Schema Definition
const typeDefs = gql`
    # Define a scalar type for file upload
    scalar Upload

    # CIN Data Type
    type CinData {
        success: Boolean!
        idNumber: String
        name: String
        lastname: String
        confidenceId: Float
        confidenceName: Float
        confidenceLastname: Float
        error: String
    }

    # Plate Detection Type
    type PlateData {
        success: Boolean!
        plateNumber: String
        confidence: Float
        error: String
    }

    # Entry/Exit Registration Type
    type RegistrationData {
        success: Boolean!
        cinData: CinData
        plateData: PlateData
        registrationId: String
        timestamp: String
        type: String  # "entry" or "exit"
        error: String
    }

    # Root Query Type
    type Query {
        healthCheck: String!
    }

    # Root Mutation Type
    type Mutation {
        extractCinData(image: Upload!): CinData!
        detectPlate(image: Upload!): PlateData!
        registerEntry(cinImage: Upload!, vehicleImage: Upload!): RegistrationData!
        registerExit(cinImage: Upload!, vehicleImage: Upload!): RegistrationData!
    }
`;

// Resolver functions
const resolvers = {
    Upload: GraphQLUpload,

    Query: {
        healthCheck: () => 'GraphQL API is operational',
    },

    Mutation: {
        extractCinData: async (_, { image }) => {
            try {
                // Process uploaded file
                const { createReadStream, filename } = await image;
                const uploadDir = path.join(__dirname, '../uploads');
                
                // Ensure upload directory exists
                if (!fs.existsSync(uploadDir)) {
                    fs.mkdirSync(uploadDir, { recursive: true });
                }
                
                const filePath = path.join(uploadDir, `${Date.now()}-${filename}`);
                const fileStream = createReadStream();
                
                // Save file to disk
                await new Promise((resolve, reject) => {
                    const writeStream = fs.createWriteStream(filePath);
                    fileStream.pipe(writeStream);
                    writeStream.on('finish', resolve);
                    writeStream.on('error', reject);
                });
                
                // Read file as buffer and send to gRPC service
                const imageBuffer = fs.readFileSync(filePath);
                const result = await cinClient.extractCinData(imageBuffer, filename);
                
                // Clean up uploaded file
                fs.unlink(filePath, err => {
                    if (err) console.error(`Error deleting file ${filePath}:`, err);
                });
                
                return result;
            } catch (error) {
                console.error('Error in extractCinData resolver:', error);
                return {
                    success: false,
                    error: `CIN extraction failed: ${error.message || error}`
                };
            }
        },

        detectPlate: async (_, { image }) => {
            try {
                // Process uploaded file
                const { createReadStream, filename } = await image;
                const uploadDir = path.join(__dirname, '../uploads');
                
                // Ensure upload directory exists
                if (!fs.existsSync(uploadDir)) {
                    fs.mkdirSync(uploadDir, { recursive: true });
                }
                
                const filePath = path.join(uploadDir, `${Date.now()}-${filename}`);
                const fileStream = createReadStream();
                
                // Save file to disk
                await new Promise((resolve, reject) => {
                    const writeStream = fs.createWriteStream(filePath);
                    fileStream.pipe(writeStream);
                    writeStream.on('finish', resolve);
                    writeStream.on('error', reject);
                });
                
                // Read file as buffer and send to gRPC service
                const imageBuffer = fs.readFileSync(filePath);
                const result = await plateClient.detectPlate(imageBuffer, filename);
                
                // Clean up uploaded file
                fs.unlink(filePath, err => {
                    if (err) console.error(`Error deleting file ${filePath}:`, err);
                });
                
                return result;
            } catch (error) {
                console.error('Error in detectPlate resolver:', error);
                return {
                    success: false,
                    error: `Plate detection failed: ${error.message || error}`
                };
            }
        },        registerEntry: async (_, { cinImage, vehicleImage }) => {
            try {
                // Process CIN image
                const { createReadStream: cinCreateReadStream, filename: cinFilename } = await cinImage;
                const uploadDir = path.join(__dirname, '../uploads');
                
                // Ensure upload directory exists
                if (!fs.existsSync(uploadDir)) {
                    fs.mkdirSync(uploadDir, { recursive: true });
                }
                
                const cinFilePath = path.join(uploadDir, `${Date.now()}-cin-${cinFilename}`);
                const cinFileStream = cinCreateReadStream();
                
                // Save CIN file to disk
                await new Promise((resolve, reject) => {
                    const writeStream = fs.createWriteStream(cinFilePath);
                    cinFileStream.pipe(writeStream);
                    writeStream.on('finish', resolve);
                    writeStream.on('error', reject);
                });
                
                // Process Vehicle image
                const { createReadStream: vehicleCreateReadStream, filename: vehicleFilename } = await vehicleImage;
                const vehicleFilePath = path.join(uploadDir, `${Date.now()}-vehicle-${vehicleFilename}`);
                const vehicleFileStream = vehicleCreateReadStream();
                
                // Save Vehicle file to disk
                await new Promise((resolve, reject) => {
                    const writeStream = fs.createWriteStream(vehicleFilePath);
                    vehicleFileStream.pipe(writeStream);
                    writeStream.on('finish', resolve);
                    writeStream.on('error', reject);
                });
                
                // Read files as buffers
                const cinImageBuffer = fs.readFileSync(cinFilePath);
                const vehicleImageBuffer = fs.readFileSync(vehicleFilePath);
                
                // Use aggregator client to process the registration
                const result = await aggregatorClient.registerEntry(
                    cinImageBuffer,
                    cinFilename,
                    vehicleImageBuffer,
                    vehicleFilename
                );
                  // Clean up uploaded files
                fs.unlink(cinFilePath, err => {
                    if (err) console.error(`Error deleting file ${cinFilePath}:`, err);
                });
                fs.unlink(vehicleFilePath, err => {
                    if (err) console.error(`Error deleting file ${vehicleFilePath}:`, err);
                });
                
                return result;
            } catch (error) {
                console.error('Error in registerEntry resolver:', error);
                return {
                    success: false,
                    error: `Entry registration failed: ${error.message || error}`,
                    type: 'entry'
                };
            }
        },        registerExit: async (_, { cinImage, vehicleImage }) => {
            try {
                // Process CIN image
                const { createReadStream: cinCreateReadStream, filename: cinFilename } = await cinImage;
                const uploadDir = path.join(__dirname, '../uploads');
                
                // Ensure upload directory exists
                if (!fs.existsSync(uploadDir)) {
                    fs.mkdirSync(uploadDir, { recursive: true });
                }
                
                const cinFilePath = path.join(uploadDir, `${Date.now()}-cin-${cinFilename}`);
                const cinFileStream = cinCreateReadStream();
                
                // Save CIN file to disk
                await new Promise((resolve, reject) => {
                    const writeStream = fs.createWriteStream(cinFilePath);
                    cinFileStream.pipe(writeStream);
                    writeStream.on('finish', resolve);
                    writeStream.on('error', reject);
                });
                
                // Process Vehicle image
                const { createReadStream: vehicleCreateReadStream, filename: vehicleFilename } = await vehicleImage;
                const vehicleFilePath = path.join(uploadDir, `${Date.now()}-vehicle-${vehicleFilename}`);
                const vehicleFileStream = vehicleCreateReadStream();
                
                // Save Vehicle file to disk
                await new Promise((resolve, reject) => {
                    const writeStream = fs.createWriteStream(vehicleFilePath);
                    vehicleFileStream.pipe(writeStream);
                    writeStream.on('finish', resolve);
                    writeStream.on('error', reject);
                });
                
                // Read files as buffers
                const cinImageBuffer = fs.readFileSync(cinFilePath);
                const vehicleImageBuffer = fs.readFileSync(vehicleFilePath);
                
                // Use aggregator client to process the registration
                const result = await aggregatorClient.registerExit(
                    cinImageBuffer,
                    cinFilename,
                    vehicleImageBuffer,
                    vehicleFilename
                );
                
                // Clean up uploaded files
                fs.unlink(cinFilePath, err => {
                    if (err) console.error(`Error deleting file ${cinFilePath}:`, err);
                });
                fs.unlink(vehicleFilePath, err => {
                    if (err) console.error(`Error deleting file ${vehicleFilePath}:`, err);
                });
                
                return result;
            } catch (error) {
                console.error('Error in registerExit resolver:', error);
                return {
                    success: false,
                    error: `Exit registration failed: ${error.message || error}`,
                    type: 'exit'
                };
            }
        },
    }
};

module.exports = { typeDefs, resolvers };
