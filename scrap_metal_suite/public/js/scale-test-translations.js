/**
 * Scale Test Page Translations
 * Extends POS_I18N with scale configuration specific translations
 */

(function() {
    // Wait for POS_I18N to be available
    if (typeof POS_I18N === 'undefined') {
        console.error('POS_I18N not loaded. Include pos-translations.js first.');
        return;
    }

    // English translations for scale-test
    const scaleTestEN = {
        // Page title
        scaleConfigTitle: 'Scale Configuration',
        scaleConfigDesc: 'Auto-detect scale settings and configure unit conversion',

        // Browser warning
        webSerialNotSupported: 'WebSerial API Not Supported',
        useChromeOrEdge: 'Please use Chrome, Edge, or Opera browser to configure scales.',

        // Step 1: Scale selection
        selectScaleTitle: 'Select Scale',
        scaleToConfig: 'Scale to Configure',
        selectScalePlaceholder: '-- Select a scale --',
        selectScaleHelp: 'Select the scale you want to configure from the database',

        // Step 2: Connection
        step1Title: 'Detect Scale Connection',
        autoDetectScale: 'Auto-Detect Scale',
        disconnect: 'Disconnect',
        disconnected: 'Disconnected',
        connected: 'Connected',
        detecting: 'Detecting...',
        baudRate: 'Baud Rate',
        dataBits: 'Data Bits',
        parity: 'Parity',
        stopBits: 'Stop Bits',
        protocol: 'Protocol',

        // Step 3: Live reading
        step2Title: 'Live Scale Reading',
        rawValueFromScale: 'raw value from scale',
        connectToSeeReading: 'Connect scale to see live reading',
        stable: 'STABLE',
        measuring: 'Measuring...',
        rawValueInfo: 'This shows the <strong>raw value</strong> from the scale signal before conversion. Use this to determine what unit the scale sends.',

        // Step 4: Calibration
        step3Title: 'Unit Calibration',
        calibrationInstruction: 'Place exactly <strong>1 kg</strong> on the scale, then enter the reading below. This helps us calculate the conversion factor.',
        oneKgShows: 'When I place <strong>1 kg</strong> on the scale, it shows:',
        useCurrentReading: 'Use Current Reading',
        detectedUnit: 'Scale signal unit (detected)',
        conversionFactor: 'Conversion factor',
        verification: 'Verification',
        unitKg: 'kg',
        unitGrams: 'grams',
        unitTons: 'tons',
        unitLb: 'lb (pounds)',
        unitUnknown: 'unknown',

        // Step 5: Save
        step4Title: 'Save Configuration',
        configSummary: 'Configuration Summary',
        summaryScale: 'Scale',
        summarySerial: 'Serial Settings',
        summaryConversion: 'Conversion Factor',
        saveToDatabase: 'Save to Database',
        configSavedSuccess: 'Configuration saved successfully!',

        // Connection log
        connectionLog: 'Connection Log',
        readyToConfigure: 'Ready to configure scale...',

        // Messages
        scaleDetected: 'Scale detected!',
        detectionFailed: 'Detection failed',
        savingConfig: 'Saving configuration...',
        saveSuccess: 'Configuration saved successfully!',
        saveFailed: 'Save failed',
        noWeightReading: 'No weight reading available. Connect to scale first.',
        selectScaleFirst: 'Please select a scale first',
        detectConfigFirst: 'Please detect scale configuration first',
        startingContinuousRead: 'Starting continuous weight reading...',
        webSerialAvailable: 'WebSerial API available',
        loadedScales: 'Loaded {count} scale(s) from database',
        noScalesInDb: 'No scales found in database. Create a Scale record first.',
        errorLoadingScales: 'Error loading scales'
    };

    // Thai translations for scale-test
    const scaleTestTH = {
        // Page title
        scaleConfigTitle: 'ตั้งค่าเครื่องชั่ง',
        scaleConfigDesc: 'ตรวจจับการตั้งค่าเครื่องชั่งอัตโนมัติและกำหนดค่าการแปลงหน่วย',

        // Browser warning
        webSerialNotSupported: 'ไม่รองรับ WebSerial API',
        useChromeOrEdge: 'กรุณาใช้ Chrome, Edge หรือ Opera เพื่อตั้งค่าเครื่องชั่ง',

        // Step 1: Scale selection
        selectScaleTitle: 'เลือกเครื่องชั่ง',
        scaleToConfig: 'เครื่องชั่งที่ต้องการตั้งค่า',
        selectScalePlaceholder: '-- เลือกเครื่องชั่ง --',
        selectScaleHelp: 'เลือกเครื่องชั่งที่ต้องการตั้งค่าจากฐานข้อมูล',

        // Step 2: Connection
        step1Title: 'ตรวจจับการเชื่อมต่อเครื่องชั่ง',
        autoDetectScale: 'ตรวจจับอัตโนมัติ',
        disconnect: 'ยกเลิกการเชื่อมต่อ',
        disconnected: 'ไม่ได้เชื่อมต่อ',
        connected: 'เชื่อมต่อแล้ว',
        detecting: 'กำลังตรวจจับ...',
        baudRate: 'อัตราบอด',
        dataBits: 'บิตข้อมูล',
        parity: 'พาริตี้',
        stopBits: 'สต็อปบิต',
        protocol: 'โปรโตคอล',

        // Step 3: Live reading
        step2Title: 'การอ่านค่าเครื่องชั่งสด',
        rawValueFromScale: 'ค่าดิบจากเครื่องชั่ง',
        connectToSeeReading: 'เชื่อมต่อเครื่องชั่งเพื่อดูค่า',
        stable: 'คงที่',
        measuring: 'กำลังวัด...',
        rawValueInfo: 'แสดง<strong>ค่าดิบ</strong>จากสัญญาณเครื่องชั่งก่อนแปลงหน่วย ใช้เพื่อระบุหน่วยที่เครื่องชั่งส่งมา',

        // Step 4: Calibration
        step3Title: 'ปรับเทียบหน่วย',
        calibrationInstruction: 'วาง <strong>1 กก.</strong> บนเครื่องชั่ง แล้วกรอกค่าที่อ่านได้ด้านล่าง เพื่อคำนวณตัวคูณแปลงหน่วย',
        oneKgShows: 'เมื่อวาง <strong>1 กก.</strong> บนเครื่องชั่ง ค่าที่แสดงคือ:',
        useCurrentReading: 'ใช้ค่าปัจจุบัน',
        detectedUnit: 'หน่วยสัญญาณ (ตรวจจับ)',
        conversionFactor: 'ตัวคูณแปลงหน่วย',
        verification: 'ตรวจสอบ',
        unitKg: 'กก.',
        unitGrams: 'กรัม',
        unitTons: 'ตัน',
        unitLb: 'ปอนด์',
        unitUnknown: 'ไม่ทราบ',

        // Step 5: Save
        step4Title: 'บันทึกการตั้งค่า',
        configSummary: 'สรุปการตั้งค่า',
        summaryScale: 'เครื่องชั่ง',
        summarySerial: 'การตั้งค่าซีเรียล',
        summaryConversion: 'ตัวคูณแปลงหน่วย',
        saveToDatabase: 'บันทึกลงฐานข้อมูล',
        configSavedSuccess: 'บันทึกการตั้งค่าสำเร็จ!',

        // Connection log
        connectionLog: 'บันทึกการเชื่อมต่อ',
        readyToConfigure: 'พร้อมตั้งค่าเครื่องชั่ง...',

        // Messages
        scaleDetected: 'ตรวจพบเครื่องชั่งแล้ว!',
        detectionFailed: 'ตรวจจับไม่สำเร็จ',
        savingConfig: 'กำลังบันทึกการตั้งค่า...',
        saveSuccess: 'บันทึกการตั้งค่าสำเร็จ!',
        saveFailed: 'บันทึกไม่สำเร็จ',
        noWeightReading: 'ไม่มีค่าน้ำหนัก กรุณาเชื่อมต่อเครื่องชั่งก่อน',
        selectScaleFirst: 'กรุณาเลือกเครื่องชั่งก่อน',
        detectConfigFirst: 'กรุณาตรวจจับการตั้งค่าเครื่องชั่งก่อน',
        startingContinuousRead: 'เริ่มอ่านค่าน้ำหนักต่อเนื่อง...',
        webSerialAvailable: 'WebSerial API พร้อมใช้งาน',
        loadedScales: 'โหลดเครื่องชั่ง {count} เครื่องจากฐานข้อมูล',
        noScalesInDb: 'ไม่พบเครื่องชั่งในฐานข้อมูล กรุณาสร้างรายการเครื่องชั่งก่อน',
        errorLoadingScales: 'เกิดข้อผิดพลาดในการโหลดเครื่องชั่ง'
    };

    // Extend POS_I18N with scale-test translations
    POS_I18N.extend('en', scaleTestEN);
    POS_I18N.extend('th', scaleTestTH);

    console.log('Scale-test translations loaded');
})();
