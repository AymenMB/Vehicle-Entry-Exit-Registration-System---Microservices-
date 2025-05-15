/**
 * Database Service for Registration Management
 * This service provides a MongoDB-based database for vehicle entry/exit records
 */

const { v4: uuidv4 } = require('uuid');
const Registration = require('../models/Registration');
const connectDB = require('../config/db');

// Connect to MongoDB when the service is initialized
connectDB().catch(err => console.error('Failed to connect to MongoDB:', err));

/**
 * Get all registrations from database
 * @returns {Promise<Array>} Promise resolving to list of registration records
 */
async function getAllRegistrations() {
    try {
        const registrations = await Registration.find({}).sort({ timestamp: -1 });
        return registrations;
    } catch (error) {
        console.error('Error getting registrations from MongoDB:', error);
        return [];
    }
}

/**
 * Save a new registration to the database
 * @param {Object} registration - Registration data object
 * @returns {Promise<boolean>} Promise resolving to success status
 */
async function saveRegistration(registration) {
    try {
        // Make sure registration has a unique ID
        if (!registration.registrationId) {
            registration.registrationId = uuidv4();
        }
        
        // Add current timestamp if not provided
        if (!registration.timestamp) {
            registration.timestamp = new Date().toISOString();
        }

        // Create new registration document
        const newRegistration = new Registration(registration);
        await newRegistration.save();
        
        console.log(`Registration saved successfully to MongoDB: ${registration.registrationId}`);
        return true;
    } catch (error) {
        console.error('Error saving registration to MongoDB:', error);
        return false;
    }
}

/**
 * Delete a registration by ID
 * @param {string} registrationId - ID of registration to delete
 * @returns {Promise<boolean>} Promise resolving to success status
 */
async function deleteRegistration(registrationId) {
    try {
        const result = await Registration.deleteOne({ registrationId });
        
        // Check if any document was deleted
        if (result.deletedCount === 0) {
            console.log(`No registration found with ID: ${registrationId}`);
            return false;
        }
        
        console.log(`Registration deleted successfully from MongoDB: ${registrationId}`);
        return true;
    } catch (error) {
        console.error('Error deleting registration from MongoDB:', error);
        return false;
    }
}

/**
 * Find a registration by ID
 * @param {string} registrationId - ID of registration to find
 * @returns {Promise<Object|null>} Promise resolving to registration object or null if not found
 */
async function getRegistrationById(registrationId) {
    try {
        const registration = await Registration.findOne({ registrationId });
        return registration;
    } catch (error) {
        console.error('Error finding registration by ID in MongoDB:', error);
        return null;
    }
}

/**
 * Get statistics about registrations from database
 * @returns {Promise<Object>} Promise resolving to statistics object
 */
async function getRegistrationStats() {
    try {
        // Get total counts
        const totalCount = await Registration.countDocuments();
        const entryCount = await Registration.countDocuments({ type: 'entry' });
        const exitCount = await Registration.countDocuments({ type: 'exit' });
        
        // Get unique vehicles and persons
        const uniquePlates = await Registration.distinct('plateData.plateNumber');
        const uniqueVehicles = uniquePlates.filter(Boolean).length;
        
        const uniqueIds = await Registration.distinct('cinData.idNumber');
        const uniquePersons = uniqueIds.filter(Boolean).length;
        
        // Get today's counts
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const todayCondition = { timestamp: { $gte: today } };
        
        const todayEntries = await Registration.countDocuments({ ...todayCondition, type: 'entry' });
        const todayExits = await Registration.countDocuments({ ...todayCondition, type: 'exit' });
        
        // Get latest registration
        const latestRegistration = await Registration.findOne().sort({ timestamp: -1 });
        
        return {
            total: totalCount,
            entries: entryCount,
            exits: exitCount,
            uniqueVehicles,
            uniquePersons,
            today: {
                entries: todayEntries,
                exits: todayExits,
                total: todayEntries + todayExits
            },
            latestRegistration: latestRegistration ? latestRegistration.timestamp : null
        };
    } catch (error) {
        console.error('Error getting registration stats from MongoDB:', error);
        return {
            total: 0,
            entries: 0,
            exits: 0,
            uniqueVehicles: 0,
            uniquePersons: 0,
            today: { entries: 0, exits: 0, total: 0 },
            latestRegistration: null
        };
    }
}

// Export all functions
module.exports = {
    getAllRegistrations,
    getRegistrationById,
    saveRegistration,
    deleteRegistration,
    getRegistrationStats
};