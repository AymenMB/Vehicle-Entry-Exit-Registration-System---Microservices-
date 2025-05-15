/**
 * MongoDB Connection Configuration
 */
const mongoose = require('mongoose');

// MongoDB connection string - update this with your MongoDB connection details
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/vehicle_registration_system';

// Connection options
const options = {
  useNewUrlParser: true,
  useUnifiedTopology: true,
};

// Connect to MongoDB
const connectDB = async () => {
  try {
    const conn = await mongoose.connect(MONGODB_URI, options);
    console.log(`MongoDB Connected: ${conn.connection.host}`);
    return conn;
  } catch (error) {
    console.error(`Error connecting to MongoDB: ${error.message}`);
    process.exit(1);
  }
};

module.exports = connectDB;
