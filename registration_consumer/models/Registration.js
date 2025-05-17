/**
 * MongoDB Schema for Vehicle Registrations - Consumer Service
 */
const mongoose = require('mongoose');

// Define the schema for the registration records
const registrationSchema = new mongoose.Schema({
  registrationId: {
    type: String,
    required: true,
    unique: true
  },
  type: {
    type: String,
    enum: ['entry', 'exit'],
    required: true
  },
  plateData: {
    plateNumber: String,
    confidence: Number,
    region: String,
    vehicleType: String,
    detectedAt: Date
  },  cinData: {
    idNumber: String,
    firstName: String,
    lastName: String,
    fullName: String,
    birthDate: String,
    expiryDate: String,
    extractedAt: Date
  },
  images: {
    plate: String,
    cin: String,
    vehicle: String
  },
  timestamp: {
    type: Date,
    default: Date.now
  },
  processed: {
    type: Boolean,
    default: true
  }
}, {
  // Enable automatic timestamps
  timestamps: true,
  // Allow additional fields not defined in schema
  strict: false
});

// Create the model from the schema
const Registration = mongoose.model('Registration', registrationSchema);

module.exports = Registration;
