/**
 * MongoDB Schema for Vehicle Registrations
 */
const mongoose = require('mongoose');

// Define the schema for the registration records
const registrationSchema = new mongoose.Schema({
  registrationId: {
    type: String,
    required: true,
    unique: true
  },
  vehicleId: {
    type: String,
    required: false
  },
  plateNumber: {
    type: String,
    required: false
  },
  cinNumber: {
    type: String,
    required: false
  },
  fullName: {
    type: String,
    required: false
  },
  entryTime: {
    type: Date,
    required: false
  },
  exitTime: {
    type: Date,
    required: false
  },
  vehicleType: {
    type: String,
    required: false
  },
  status: {
    type: String,
    enum: ['entered', 'exited', 'pending'],
    default: 'pending'
  },
  timestamp: {
    type: Date,
    default: Date.now
  },
  images: {
    plate: String,
    cin: String,
    vehicle: String
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
