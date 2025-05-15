const express = require('express');
const router = express.Router();
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const cinClient = require('../services/cin_client');
const plateClient = require('../services/plate_client');
const aggregatorClient = require('../services/aggregator_client');
const dbService = require('../services/db_service');
const kafkaProducer = require('../services/kafka_producer');
const { v4: uuidv4 } = require('uuid');

// Connect to Kafka when the router is loaded
kafkaProducer.connect().catch(err => {
    console.error('Failed to connect to Kafka on startup:', err);
});

// Configure multer for file uploads
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, path.join(__dirname, '../uploads/'));
    },
    filename: function (req, file, cb) {
        cb(null, `${Date.now()}-${file.originalname}`);
    }
});

const upload = multer({ storage: storage });

// Health check endpoint
router.get('/health', (req, res) => {
    res.json({ status: 'ok', message: 'REST API is operational' });
});

/**
 * @api {get} /api/stats Get database statistics
 * @apiName GetStats
 * @apiGroup Statistics
 * @apiDescription Get statistics about registrations from the database
 * 
 * @apiSuccess {Boolean} success Whether the request was successful
 * @apiSuccess {Object} stats Statistics about registrations
 */
router.get('/stats', async (req, res) => {
    try {
        const stats = await dbService.getRegistrationStats();
        
        res.status(200).json({ 
            success: true, 
            stats: stats 
        });
    } catch (error) {
        console.error('Error getting stats:', error);
        res.status(500).json({ 
            success: false, 
            error: `Failed to get stats: ${error.message || error}` 
        });
    }
});

/**
 * @api {post} /api/cin/extract Extract CIN data
 * @apiName ExtractCIN
 * @apiGroup CIN
 * @apiDescription Extract information from a CIN (ID card) image
 * 
 * @apiParam {File} image CIN image file
 * 
 * @apiSuccess {Boolean} success Whether the extraction was successful
 * @apiSuccess {String} idNumber Extracted ID number
 * @apiSuccess {String} name Extracted name
 * @apiSuccess {String} lastname Extracted lastname
 * @apiSuccess {Number} confidenceId Confidence score for ID number
 * @apiSuccess {Number} confidenceName Confidence score for name
 * @apiSuccess {Number} confidenceLastname Confidence score for lastname
 * @apiSuccess {String} error Error message if any
 */
router.post('/cin/extract', upload.single('image'), async (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ success: false, error: 'No image file provided' });
        }

        const imagePath = req.file.path;
        const imageBuffer = fs.readFileSync(imagePath);

        const result = await cinClient.extractCinData(imageBuffer, req.file.originalname);
        
        // Clean up uploaded file
        fs.unlink(imagePath, (err) => {
            if (err) console.error(`Error deleting file ${imagePath}:`, err);
        });

        res.status(200).json(result);
    } catch (error) {
        console.error('Error in /cin/extract:', error);
        res.status(500).json({ 
            success: false, 
            error: `CIN extraction failed: ${error.message || error}` 
        });
    }
});

/**
 * @api {post} /api/plate/detect Detect license plate
 * @apiName DetectPlate
 * @apiGroup Plate
 * @apiDescription Detect license plate from a vehicle image
 * 
 * @apiParam {File} image Vehicle image file
 * 
 * @apiSuccess {Boolean} success Whether the detection was successful
 * @apiSuccess {String} plateNumber Detected license plate number
 * @apiSuccess {Number} confidence Confidence score
 * @apiSuccess {String} error Error message if any
 */
router.post('/plate/detect', upload.single('image'), async (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ success: false, error: 'No image file provided' });
        }

        const imagePath = req.file.path;
        const imageBuffer = fs.readFileSync(imagePath);

        const result = await plateClient.detectPlate(imageBuffer, req.file.originalname);
        
        // Clean up uploaded file
        fs.unlink(imagePath, (err) => {
            if (err) console.error(`Error deleting file ${imagePath}:`, err);
        });

        res.status(200).json(result);
    } catch (error) {
        console.error('Error in /plate/detect:', error);
        res.status(500).json({ 
            success: false, 
            error: `Plate detection failed: ${error.message || error}` 
        });
    }
});

/**
 * @api {post} /api/entry/register Register vehicle entry
 * @apiName RegisterEntry
 * @apiGroup Entry
 * @apiDescription Process both CIN and license plate together for entry registration
 * 
 * @apiParam {File} cinImage CIN image file
 * @apiParam {File} vehicleImage Vehicle image file
 * 
 * @apiSuccess {Boolean} success Whether the registration was successful
 * @apiSuccess {Object} cinData Extracted CIN data
 * @apiSuccess {Object} plateData Detected license plate data
 * @apiSuccess {String} entryId Generated entry ID
 * @apiSuccess {String} timestamp Entry timestamp
 */
router.post('/entry/register', upload.fields([
    { name: 'cinImage', maxCount: 1 },
    { name: 'vehicleImage', maxCount: 1 }
]), async (req, res) => {
    try {
        if (!req.files || !req.files.cinImage || !req.files.vehicleImage) {
            return res.status(400).json({ 
                success: false, 
                error: 'Both CIN image and vehicle image are required' 
            });
        }

        const cinImagePath = req.files.cinImage[0].path;
        const vehicleImagePath = req.files.vehicleImage[0].path;
        
        const cinImageBuffer = fs.readFileSync(cinImagePath);
        const vehicleImageBuffer = fs.readFileSync(vehicleImagePath);

        // Process both images in parallel
        const [cinResult, plateResult] = await Promise.all([
            cinClient.extractCinData(cinImageBuffer, req.files.cinImage[0].originalname),
            plateClient.detectPlate(vehicleImageBuffer, req.files.vehicleImage[0].originalname)
        ]);

        // Clean up uploaded files
        fs.unlink(cinImagePath, (err) => {
            if (err) console.error(`Error deleting file ${cinImagePath}:`, err);
        });
        fs.unlink(vehicleImagePath, (err) => {
            if (err) console.error(`Error deleting file ${vehicleImagePath}:`, err);
        });

        const entryId = `ENTRY-${Date.now()}`;
        const timestamp = new Date().toISOString();

        res.status(200).json({
            success: true,
            cinData: cinResult,
            plateData: plateResult,
            entryId: entryId,
            timestamp: timestamp
        });
    } catch (error) {
        console.error('Error in /entry/register:', error);
        res.status(500).json({ 
            success: false, 
            error: `Entry registration failed: ${error.message || error}` 
        });
    }
});

/**
 * @api {post} /api/exit/register Register vehicle exit
 * @apiName RegisterExit
 * @apiGroup Exit
 * @apiDescription Process both CIN and license plate together for exit registration
 * 
 * @apiParam {File} cinImage CIN image file
 * @apiParam {File} vehicleImage Vehicle image file
 * 
 * @apiSuccess {Boolean} success Whether the registration was successful
 * @apiSuccess {Object} cinData Extracted CIN data
 * @apiSuccess {Object} plateData Detected license plate data
 * @apiSuccess {String} exitId Generated exit ID
 * @apiSuccess {String} timestamp Exit timestamp
 */
router.post('/exit/register', upload.fields([
    { name: 'cinImage', maxCount: 1 },
    { name: 'vehicleImage', maxCount: 1 }
]), async (req, res) => {
    try {
        if (!req.files || !req.files.cinImage || !req.files.vehicleImage) {
            return res.status(400).json({ 
                success: false, 
                error: 'Both CIN image and vehicle image are required' 
            });
        }

        const cinImagePath = req.files.cinImage[0].path;
        const vehicleImagePath = req.files.vehicleImage[0].path;
        
        const cinImageBuffer = fs.readFileSync(cinImagePath);
        const vehicleImageBuffer = fs.readFileSync(vehicleImagePath);

        // Process both images in parallel
        const [cinResult, plateResult] = await Promise.all([
            cinClient.extractCinData(cinImageBuffer, req.files.cinImage[0].originalname),
            plateClient.detectPlate(vehicleImageBuffer, req.files.vehicleImage[0].originalname)
        ]);

        // Clean up uploaded files
        fs.unlink(cinImagePath, (err) => {
            if (err) console.error(`Error deleting file ${cinImagePath}:`, err);
        });
        fs.unlink(vehicleImagePath, (err) => {
            if (err) console.error(`Error deleting file ${vehicleImagePath}:`, err);
        });

        const exitId = `EXIT-${Date.now()}`;
        const timestamp = new Date().toISOString();

        res.status(200).json({
            success: true,
            cinData: cinResult,
            plateData: plateResult,
            exitId: exitId,
            timestamp: timestamp
        });
    } catch (error) {
        console.error('Error in /exit/register:', error);
        res.status(500).json({ 
            success: false, 
            error: `Exit registration failed: ${error.message || error}` 
        });
    }
});

/**
 * @api {post} /api/register/entry Register vehicle entry
 * @apiName RegisterEntry
 * @apiGroup Registration
 * @apiDescription Register a vehicle entry with CIN and vehicle images
 * 
 * @apiParam {File} cinImage CIN image file
 * @apiParam {File} vehicleImage Vehicle image file
 * 
 * @apiSuccess {Boolean} success Whether the registration was successful
 * @apiSuccess {Object} cinData Extracted CIN data
 * @apiSuccess {Object} plateData Detected plate data
 * @apiSuccess {String} registrationId Unique registration ID
 * @apiSuccess {String} timestamp Registration timestamp
 * @apiSuccess {String} type Registration type (entry)
 * @apiSuccess {String} error Error message if any
 */
router.post('/register/entry', upload.fields([
    { name: 'cinImage', maxCount: 1 },
    { name: 'vehicleImage', maxCount: 1 }
]), async (req, res) => {
    try {
        if (!req.files || !req.files.cinImage || !req.files.vehicleImage) {
            return res.status(400).json({ 
                success: false, 
                error: 'Both CIN image and vehicle image are required' 
            });
        }

        const cinImagePath = req.files.cinImage[0].path;
        const vehicleImagePath = req.files.vehicleImage[0].path;
        
        // Verify files exist and are readable
        if (!fs.existsSync(cinImagePath) || !fs.existsSync(vehicleImagePath)) {
            return res.status(400).json({
                success: false,
                error: 'File upload incomplete or file not found'
            });
        }
        
        const cinImageBuffer = fs.readFileSync(cinImagePath);
        const vehicleImageBuffer = fs.readFileSync(vehicleImagePath);

        // Verify we have valid buffers
        if (!cinImageBuffer || !vehicleImageBuffer) {
            return res.status(400).json({
                success: false,
                error: 'Unable to read uploaded files'
            });
        }

        // Log file sizes for debugging
        console.log(`CIN image size: ${cinImageBuffer.length} bytes`);
        console.log(`Vehicle image size: ${vehicleImageBuffer.length} bytes`);

        const result = await aggregatorClient.registerEntry(
            cinImageBuffer,
            req.files.cinImage[0].originalname,
            vehicleImageBuffer,
            req.files.vehicleImage[0].originalname
        );
        
        // Clean up uploaded files
        fs.unlink(cinImagePath, (err) => {
            if (err) console.error(`Error deleting file ${cinImagePath}:`, err);
        });
        
        fs.unlink(vehicleImagePath, (err) => {
            if (err) console.error(`Error deleting file ${vehicleImagePath}:`, err);
        });

        // Save registration to database using db service
        if (result.success) {
            const registration = {
                registrationId: result.registrationId,
                timestamp: result.timestamp,
                type: result.type,
                cinData: result.cinData,
                plateData: result.plateData,
                date: new Date().toISOString()
            };

            try {
                dbService.saveRegistration(registration);
                
                // Send registration event to Kafka
                await kafkaProducer.sendRegistrationEvent(registration);
                
                // Send notification about the entry
                await kafkaProducer.sendNotification(
                    `Vehicle entered: ${registration.plateData?.plateNumber || 'Unknown'} by ${registration.cinData?.name || 'Unknown'} ${registration.cinData?.lastname || ''}`,
                    'info',
                    { registrationId: registration.registrationId, type: 'entry' }
                );
            } catch (error) {
                console.error('Error in Kafka operations:', error);
            }
        }

        res.status(200).json(result);
    } catch (error) {
        console.error('Error in /register/entry:', error);
        res.status(500).json({ 
            success: false, 
            error: `Entry registration failed: ${error.message || error}` 
        });
    }
});

/**
 * @api {post} /api/register/exit Register vehicle exit
 * @apiName RegisterExit
 * @apiGroup Registration
 * @apiDescription Register a vehicle exit with CIN and vehicle images
 * 
 * @apiParam {File} cinImage CIN image file
 * @apiParam {File} vehicleImage Vehicle image file
 * 
 * @apiSuccess {Boolean} success Whether the registration was successful
 * @apiSuccess {Object} cinData Extracted CIN data
 * @apiSuccess {Object} plateData Detected plate data
 * @apiSuccess {String} registrationId Unique registration ID
 * @apiSuccess {String} timestamp Registration timestamp
 * @apiSuccess {String} type Registration type (exit)
 * @apiSuccess {String} error Error message if any
 */
router.post('/register/exit', upload.fields([
    { name: 'cinImage', maxCount: 1 },
    { name: 'vehicleImage', maxCount: 1 }
]), async (req, res) => {
    try {
        if (!req.files || !req.files.cinImage || !req.files.vehicleImage) {
            return res.status(400).json({ 
                success: false, 
                error: 'Both CIN image and vehicle image are required' 
            });
        }

        const cinImagePath = req.files.cinImage[0].path;
        const vehicleImagePath = req.files.vehicleImage[0].path;
        
        // Verify files exist and are readable
        if (!fs.existsSync(cinImagePath) || !fs.existsSync(vehicleImagePath)) {
            return res.status(400).json({
                success: false,
                error: 'File upload incomplete or file not found'
            });
        }
        
        const cinImageBuffer = fs.readFileSync(cinImagePath);
        const vehicleImageBuffer = fs.readFileSync(vehicleImagePath);

        // Verify we have valid buffers
        if (!cinImageBuffer || !vehicleImageBuffer) {
            return res.status(400).json({
                success: false,
                error: 'Unable to read uploaded files'
            });
        }

        // Log file sizes for debugging
        console.log(`CIN image size: ${cinImageBuffer.length} bytes`);
        console.log(`Vehicle image size: ${vehicleImageBuffer.length} bytes`);

        const result = await aggregatorClient.registerExit(
            cinImageBuffer,
            req.files.cinImage[0].originalname,
            vehicleImageBuffer,
            req.files.vehicleImage[0].originalname
        );
        
        // Clean up uploaded files
        fs.unlink(cinImagePath, (err) => {
            if (err) console.error(`Error deleting file ${cinImagePath}:`, err);
        });
        
        fs.unlink(vehicleImagePath, (err) => {
            if (err) console.error(`Error deleting file ${vehicleImagePath}:`, err);
        });

        // Save registration to database using db service
        if (result.success) {
            const registration = {
                registrationId: result.registrationId,
                timestamp: result.timestamp,
                type: result.type,
                cinData: result.cinData,
                plateData: result.plateData,
                date: new Date().toISOString()
            };

            try {
                dbService.saveRegistration(registration);
                
                // Send registration event to Kafka
                await kafkaProducer.sendRegistrationEvent(registration);
                
                // Send notification about the exit
                await kafkaProducer.sendNotification(
                    `Vehicle exited: ${registration.plateData?.plateNumber || 'Unknown'} by ${registration.cinData?.name || 'Unknown'} ${registration.cinData?.lastname || ''}`,
                    'info',
                    { registrationId: registration.registrationId, type: 'exit' }
                );
            } catch (error) {
                console.error('Error in Kafka operations:', error);
            }
        }

        res.status(200).json(result);
    } catch (error) {
        console.error('Error in /register/exit:', error);
        res.status(500).json({ 
            success: false, 
            error: `Exit registration failed: ${error.message || error}` 
        });
    }
});

/**
 * @api {get} /api/status System status
 * @apiName Status
 * @apiGroup System
 * @apiDescription Get system status including all microservices
 * 
 * @apiSuccess {String} status Overall system status
 * @apiSuccess {String} cinService CIN service status
 * @apiSuccess {String} plateService Plate detection service status
 * @apiSuccess {String} error Error message if any
 */
router.get('/status', async (req, res) => {
    try {
        const result = await aggregatorClient.healthCheck();
        res.status(200).json(result);
    } catch (error) {
        console.error('Error in /status:', error);
        res.status(500).json({ 
            status: 'error', 
            error: `Status check failed: ${error.message || error}` 
        });
    }
});

/**
 * @api {get} /api/registrations Get registration history
 * @apiName GetRegistrations
 * @apiGroup Registration
 * @apiDescription Get history of vehicle registrations
 * 
 * @apiSuccess {Array} registrations List of registrations
 * @apiSuccess {String} error Error message if any
 */
router.get('/registrations', async (req, res) => {
    try {
        // Get registrations using DB service
        const registrations = await dbService.getAllRegistrations();
        
        // Sort by timestamp (newest first)
        registrations.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        
        res.status(200).json({ 
            success: true, 
            registrations: registrations 
        });
    } catch (error) {
        console.error('Error getting registrations:', error);
        res.status(500).json({ 
            success: false, 
            error: `Failed to get registrations: ${error.message || error}` 
        });
    }
});

/**
 * @api {get} /api/registrations/:id Get registration by ID
 * @apiName GetRegistrationById
 * @apiGroup Registration
 * @apiDescription Get a specific registration by ID
 * 
 * @apiParam {String} id Registration ID
 * 
 * @apiSuccess {Object} registration Registration details
 * @apiSuccess {String} error Error message if any
 */
router.get('/registrations/:id', async (req, res) => {
    try {
        const registrationId = req.params.id;
        
        // Get registration using DB service
        const registration = await dbService.getRegistrationById(registrationId);
        
        if (!registration) {
            return res.status(404).json({ 
                success: false, 
                error: `Registration with ID ${registrationId} not found` 
            });
        }
        
        res.status(200).json({ 
            success: true, 
            registration: registration 
        });
    } catch (error) {
        console.error('Error getting registration by ID:', error);
        res.status(500).json({ 
            success: false, 
            error: `Failed to get registration: ${error.message || error}` 
        });
    }
});

/**
 * @api {delete} /api/registrations/:id Delete a registration
 * @apiName DeleteRegistration
 * @apiGroup Registration
 * @apiDescription Delete a registration by ID
 * 
 * @apiParam {String} id Registration ID
 * 
 * @apiSuccess {Boolean} success Whether the deletion was successful
 * @apiSuccess {String} error Error message if any
 */
router.delete('/registrations/:id', async (req, res) => {
    try {
        const registrationId = req.params.id;
        
        // Delete registration using DB service
        const success = await dbService.deleteRegistration(registrationId);
        
        if (!success) {
            return res.status(404).json({ 
                success: false, 
                error: `Registration with ID ${registrationId} not found` 
            });
        }
        
        res.status(200).json({ 
            success: true, 
            message: `Registration ${registrationId} deleted successfully` 
        });
    } catch (error) {
        console.error('Error deleting registration:', error);
        res.status(500).json({ 
            success: false, 
            error: `Failed to delete registration: ${error.message || error}` 
        });
    }
});

/**
 * @api {post} /api/registrations Create a new registration
 * @apiName CreateRegistration
 * @apiGroup Registration
 * @apiDescription Create a new registration entry directly
 * 
 * @apiParam {Object} registration Registration data
 * 
 * @apiSuccess {Boolean} success Whether the creation was successful
 * @apiSuccess {String} message Success message
 * @apiSuccess {String} error Error message if any
 */
router.post('/registrations', express.json(), async (req, res) => {
    try {
        const registration = req.body;
        
        // Validate required fields
        if (!registration.type || !['entry', 'exit'].includes(registration.type)) {
            return res.status(400).json({
                success: false,
                error: "Registration must include a valid 'type' field ('entry' or 'exit')"
            });
        }
        
        // Save using DB service
        const success = await dbService.saveRegistration(registration);
        
        if (!success) {
            return res.status(500).json({
                success: false,
                error: "Failed to save registration"
            });
        }
        
        res.status(201).json({
            success: true,
            message: "Registration created successfully",
            registrationId: registration.registrationId
        });
    } catch (error) {
        console.error('Error creating registration:', error);
        res.status(500).json({ 
            success: false, 
            error: `Failed to create registration: ${error.message || error}` 
        });
    }
});

// The kafka_status endpoint to check Kafka connectivity
router.get('/kafka_status', async (req, res) => {
    try {
        // First check if Kafka is enabled
        if (!kafkaProducer.isKafkaEnabled()) {
            return res.status(503).json({
                status: 'disabled',
                message: 'Kafka is disabled in the current configuration.',
                details: 'To enable Kafka, run kafka_setup.bat and follow the instructions.'
            });
        }
        
        // Check Kafka connection by sending a test notification
        const isConnected = await kafkaProducer.sendNotification(
            'Kafka status check', 
            'info', 
            { source: 'api_gateway', endpoint: '/kafka_status' }
        );
        
        if (isConnected) {
            res.status(200).json({
                status: 'ok',
                message: 'Kafka connection is healthy'
            });
        } else {
            res.status(503).json({
                status: 'error',
                message: 'Failed to connect to Kafka',
                details: 'Kafka may not be running. Run kafka_setup.bat for setup instructions.'
            });
        }
    } catch (error) {
        console.error('Error checking Kafka status:', error);
        res.status(500).json({
            status: 'error',
            message: `Kafka status check failed: ${error.message || error}`,
            details: 'Check the logs for more information.'
        });
    }
});

module.exports = router;
