/**
 * POS Translations - Unified translation file for all POS pages
 * Supports: English (en), Thai (th)
 *
 * Usage:
 * 1. Include this file in your HTML: <script src="/assets/scrap_metal_suite/js/pos-translations.js"></script>
 * 2. Call POS_I18N.init() to initialize
 * 3. Use POS_I18N.t('key') to get translated string
 * 4. Use POS_I18N.setLanguage('th') to change language
 */

const POS_I18N = (function() {
    // Default language
    let currentLanguage = 'en';

    // Available languages
    const availableLanguages = ['en', 'th'];

    // Translations object
    const translations = {
        en: {
            // ===== Landing Page =====
            posTitle: 'SMT POS by X-DESK',
            activeSession: 'Active Session',
            noActiveSession: 'No Active Session',
            selectTerminal: 'Select a terminal to start a new session',
            scrapWeighing: 'Scrap Weighing',
            scrapWeighingDesc: 'Record scrap weights by item',
            truckScale: 'Truck Scale',
            truckScaleDesc: 'Record gross/tare truck weights',
            startSession: 'Start Session',
            resumeSession: 'Resume Session',
            language: 'Language',
            theme: 'Theme',
            lightMode: 'Light Mode',
            darkMode: 'Dark Mode',

            // ===== Common =====
            loading: 'Loading...',
            error: 'Error',
            success: 'Success',
            cancel: 'Cancel',
            confirm: 'Confirm',
            save: 'Save',
            close: 'Close',
            back: 'Back',
            search: 'Search',
            or: 'OR',
            total: 'Total',

            // ===== Session =====
            session: 'Session',
            sessionId: 'Session ID',
            operator: 'Operator',
            openSession: 'Open Session',
            closeSession: 'Close Session',
            endSession: 'End Session',
            confirmCloseSession: 'Are you sure you want to close this session?',
            sessionClosed: 'Session closed successfully!',
            failedToClose: 'Failed to close session',
            sessionSummary: 'Session Summary',
            summary: 'Summary',
            closeShift: 'Close Shift',

            // ===== Scale =====
            scale: 'Scale',
            selectScale: 'Select Scale',
            scanOrSelectScale: 'Scan scale QR code or select from dropdown',
            scanScaleQR: 'Scan Scale QR',
            selectFromList: 'Select from list:',
            scaleName: 'Scale:',
            scaleType: 'Type:',
            location: 'Location:',
            confirmScale: 'Confirm Scale',
            pointCameraAtScale: 'Point camera at scale QR code',
            scaleNotActive: 'Not Active',
            scaleInUse: 'In Use',
            scaleRequired: 'Please select a scale to continue',
            scaleSetSuccess: 'Scale set successfully',
            noScalesAvailable: 'No scales available',

            // ===== Orders =====
            orderId: 'Order ID',
            order: 'Order',
            orders: 'Orders',
            orderDate: 'Order Date',
            dropoffDate: 'Drop-off Date',
            orderItems: 'Order Items',
            indicatedWeight: 'Indicated Weight',
            noOrderItems: 'No items in this order',
            expectedItems: 'Expected Items',
            orderNotFound: 'Order not found',
            noOrdersFound: 'No orders found',
            errorSearching: 'Error searching for order',
            scanOrderBarcode: 'Scan order barcode/QR',
            pointCamera: 'Point camera at barcode or QR code',
            orEnterManually: 'Or enter manually:',
            enterOrderId: 'Enter order ID or scan...',
            scan: 'Scan',

            // ===== Items =====
            items: 'Items',
            item: 'Item',
            all: 'All',
            fromOrder: 'From Order',
            noItemsAdded: 'No items added yet',
            addToCart: 'Add to Cart',

            // ===== Cart =====
            cart: 'Cart',
            clearAll: 'Clear All',
            emptyCart: 'Cart is empty',

            // ===== Weight =====
            weight: 'Weight',
            weights: 'Weights',
            totalWeight: 'Total Weight:',
            recordWeight: 'Record Weight',
            weightsRecorded: 'Weights Recorded',
            weightRecorded: 'Weight recorded',
            reweight: 'Re-weight',
            reweightWarning: 'This order already has weights. Recording will be a re-weigh.',
            pleaseEnterWeight: 'Please enter a valid weight',
            failedToRecord: 'Failed to record weight',
            grossWeight: 'Gross Weight',
            tareWeight: 'Tare Weight',
            netWeight: 'Net Weight',
            recordGross: 'Record Gross',
            recordTare: 'Record Tare',

            // ===== Supplier =====
            supplier: 'Supplier',
            licensePlate: 'License Plate',

            // ===== Status =====
            status: 'Status',
            pending: 'Pending',
            completed: 'Completed',
            cancelled: 'Cancelled',

            // ===== Remarks & Photo =====
            remarks: 'Remarks',
            addRemarks: 'Add Remarks',
            enterRemarks: 'Enter remarks for this order...',
            saveRemarks: 'Save Remarks',
            remarksSaved: 'Remarks saved',
            photo: 'Photo',
            capturePhoto: 'Capture Photo',
            capture: 'Capture',
            retake: 'Retake',
            savePhoto: 'Save Photo',
            photoReady: 'Photo captured and ready to attach',
            photosAttached: 'photo(s) attached',

            // ===== Confirmation =====
            confirmRecording: 'Confirm Recording',
            confirmRecord: 'Confirm & Record',
            confirmUpdate: 'Confirm & Update',
            dateTime: 'Date & Time',
            recordedBy: 'Recorded By',

            // ===== Reweight =====
            reweightWarning: 'Previous weighing loaded. Changes will be marked as reweight.',
            reweightNotice: 'This will update the previous weighing record.',
            reweightReason: 'Reason for reweight',
            enterReweightReason: 'Enter reason for reweight...',
            previousWeighingLoaded: 'Previous weighing loaded into cart',

            // ===== Camera =====
            camera: 'Camera',
            cameraNotAvailable: 'Camera not available',
            startingCamera: 'Starting camera...',
            cameraError: 'Camera error',
            cameraPermissionDenied: 'Camera permission denied',

            // ===== Truck Terminal =====
            truckWeights: 'Truck Weights',
            selectOrderToRecordWeights: 'Select an order to record truck weights',
            grossRecorded: 'Gross weight recorded',
            tareRecorded: 'Tare weight recorded',
            netCalculated: 'Net weight calculated',
            updateGross: 'Update Gross',
            updateTare: 'Update Tare',
            recordGrossWeight: 'Record Gross Weight',
            recordTareWeight: 'Record Tare Weight',
            weighTruckWithLoad: 'Weigh the truck WITH scrap loaded',
            weighEmptyTruck: 'Weigh the EMPTY truck after unloading',
            saveWeight: 'Save Weight',
            truckWeightRemarks: 'Truck Weight Remarks',
            weightVerification: 'Weight Verification',
            netTruckWeight: 'Net Truck Weight',
            totalScrapWeight: 'Total Scrap Weight',
            variance: 'Variance',
            varianceWithinTolerance: 'Variance within tolerance',
            varianceWarning: 'Variance warning',
            varianceExceedsTolerance: 'Variance exceeds tolerance',
            scrapWeightRecords: 'Scrap Weight Records',
            confirmEndSession: 'Are you sure you want to end this session?',
            selectTruckScale: 'Select Truck Scale',
            noTruckScalesAvailable: 'No truck scales available',
            notTruckScale: 'This is not a truck scale. Please scan a truck scale.',
            scanScaleQRCode: 'Scan Scale QR Code',
            pointCameraAtScaleQR: 'Point camera at scale QR code',

            // ===== Errors & Messages =====
            connectionError: 'Connection error. Please try again.',
            serverError: 'Server error. Please contact support.',
            invalidInput: 'Invalid input',
            requiredField: 'This field is required',

            // ===== Validation Errors =====
            atLeastOneItemRequired: 'At least one item is required',
            invalidWeightValue: 'Invalid weight value for item {item}',
            weightMustBeGreaterThanZero: 'Weight must be greater than zero for item {item}',
            weightExceedsScaleCapacity: 'Weight {weight} kg exceeds scale {scale} maximum capacity of {max} kg',
            remarksExceedMaxLength: 'Remarks exceed maximum length of {max} characters',
            noActiveSession: 'No active POS session found',
            sessionNotBelongToUser: 'This session does not belong to the current user',
            invalidOrderId: 'Invalid Order ID',
            orderNotFound: 'Order not found',
            orderAlreadyCompleted: 'Order has already been completed',
            orderAlreadyWeighed: 'Order has already been weighed',
            scaleNotFound: 'Scale not found: {scale}',
            photoUploadFailed: 'Failed to upload photo',

            // ===== Units =====
            kg: 'kg',
            ton: 'ton',

            // ===== Time =====
            today: 'Today',
            yesterday: 'Yesterday',
            now: 'Now'
        },

        th: {
            // ===== Landing Page =====
            posTitle: 'SMT POS โดย X-DESK',
            activeSession: 'เซสชันที่ใช้งาน',
            noActiveSession: 'ไม่มีเซสชันที่ใช้งาน',
            selectTerminal: 'เลือกเทอร์มินัลเพื่อเริ่มเซสชันใหม่',
            scrapWeighing: 'ชั่งเศษวัสดุ',
            scrapWeighingDesc: 'บันทึกน้ำหนักเศษวัสดุตามรายการ',
            truckScale: 'เครื่องชั่งรถบรรทุก',
            truckScaleDesc: 'บันทึกน้ำหนักรวม/น้ำหนักเปล่ารถ',
            startSession: 'เริ่มเซสชัน',
            resumeSession: 'ดำเนินการต่อ',
            language: 'ภาษา',
            theme: 'ธีม',
            lightMode: 'โหมดสว่าง',
            darkMode: 'โหมดมืด',

            // ===== Common =====
            loading: 'กำลังโหลด...',
            error: 'ข้อผิดพลาด',
            success: 'สำเร็จ',
            cancel: 'ยกเลิก',
            confirm: 'ยืนยัน',
            save: 'บันทึก',
            close: 'ปิด',
            back: 'กลับ',
            search: 'ค้นหา',
            or: 'หรือ',
            total: 'รวม',

            // ===== Session =====
            session: 'เซสชัน',
            sessionId: 'รหัสเซสชัน',
            operator: 'พนักงาน',
            openSession: 'เปิดเซสชัน',
            closeSession: 'ปิดเซสชัน',
            endSession: 'สิ้นสุดเซสชัน',
            confirmCloseSession: 'คุณต้องการปิดเซสชันนี้หรือไม่?',
            sessionClosed: 'ปิดเซสชันสำเร็จ!',
            failedToClose: 'ไม่สามารถปิดเซสชันได้',
            sessionSummary: 'สรุปเซสชัน',
            summary: 'สรุป',
            closeShift: 'ปิดกะ',

            // ===== Scale =====
            scale: 'เครื่องชั่ง',
            selectScale: 'เลือกเครื่องชั่ง',
            scanOrSelectScale: 'สแกน QR เครื่องชั่งหรือเลือกจากรายการ',
            scanScaleQR: 'สแกน QR เครื่องชั่ง',
            selectFromList: 'เลือกจากรายการ:',
            scaleName: 'เครื่องชั่ง:',
            scaleType: 'ประเภท:',
            location: 'ตำแหน่ง:',
            confirmScale: 'ยืนยันเครื่องชั่ง',
            pointCameraAtScale: 'เล็งกล้องไปที่ QR เครื่องชั่ง',
            scaleNotActive: 'ไม่พร้อมใช้งาน',
            scaleInUse: 'กำลังใช้งาน',
            scaleRequired: 'กรุณาเลือกเครื่องชั่งเพื่อดำเนินการต่อ',
            scaleSetSuccess: 'ตั้งค่าเครื่องชั่งสำเร็จ',
            noScalesAvailable: 'ไม่มีเครื่องชั่งที่พร้อมใช้งาน',

            // ===== Orders =====
            orderId: 'รหัสออเดอร์',
            order: 'ออเดอร์',
            orders: 'ออเดอร์',
            orderDate: 'วันที่สั่ง',
            dropoffDate: 'วันที่ส่งมอบ',
            orderItems: 'รายการสินค้า',
            indicatedWeight: 'น้ำหนักที่แจ้ง',
            noOrderItems: 'ไม่มีรายการในออเดอร์นี้',
            expectedItems: 'รายการที่คาดหวัง',
            orderNotFound: 'ไม่พบออเดอร์',
            noOrdersFound: 'ไม่พบออเดอร์',
            errorSearching: 'เกิดข้อผิดพลาดในการค้นหา',
            scanOrderBarcode: 'สแกนบาร์โค้ด/QR ออเดอร์',
            pointCamera: 'เล็งกล้องไปที่บาร์โค้ดหรือ QR โค้ด',
            orEnterManually: 'หรือกรอกเอง:',
            enterOrderId: 'กรอกรหัสออเดอร์หรือสแกน...',
            scan: 'สแกน',

            // ===== Items =====
            items: 'รายการสินค้า',
            item: 'สินค้า',
            all: 'ทั้งหมด',
            fromOrder: 'จากออเดอร์',
            noItemsAdded: 'ยังไม่มีรายการ',
            addToCart: 'เพิ่มลงตะกร้า',

            // ===== Cart =====
            cart: 'ตะกร้า',
            clearAll: 'ล้างทั้งหมด',
            emptyCart: 'ตะกร้าว่าง',

            // ===== Weight =====
            weight: 'น้ำหนัก',
            weights: 'น้ำหนัก',
            totalWeight: 'น้ำหนักรวม:',
            recordWeight: 'บันทึกน้ำหนัก',
            weightsRecorded: 'จำนวนครั้งที่ชั่ง',
            weightRecorded: 'บันทึกน้ำหนักแล้ว',
            reweight: 'ชั่งซ้ำ',
            reweightWarning: 'ออเดอร์นี้ถูกบันทึกแล้ว การบันทึกจะเป็นการชั่งซ้ำ',
            pleaseEnterWeight: 'กรุณากรอกน้ำหนักที่ถูกต้อง',
            failedToRecord: 'ไม่สามารถบันทึกน้ำหนักได้',
            grossWeight: 'น้ำหนักรวม',
            tareWeight: 'น้ำหนักเปล่า',
            netWeight: 'น้ำหนักสุทธิ',
            recordGross: 'บันทึกน้ำหนักรวม',
            recordTare: 'บันทึกน้ำหนักเปล่า',

            // ===== Supplier =====
            supplier: 'ผู้ขาย',
            licensePlate: 'ป้ายทะเบียน',

            // ===== Status =====
            status: 'สถานะ',
            pending: 'รอดำเนินการ',
            completed: 'เสร็จสิ้น',
            cancelled: 'ยกเลิก',

            // ===== Remarks & Photo =====
            remarks: 'หมายเหตุ',
            addRemarks: 'เพิ่มหมายเหตุ',
            enterRemarks: 'กรอกหมายเหตุสำหรับออเดอร์นี้...',
            saveRemarks: 'บันทึกหมายเหตุ',
            remarksSaved: 'บันทึกหมายเหตุแล้ว',
            photo: 'ถ่ายรูป',
            capturePhoto: 'ถ่ายรูป',
            capture: 'ถ่าย',
            retake: 'ถ่ายใหม่',
            savePhoto: 'บันทึกรูป',
            photoReady: 'ถ่ายรูปแล้ว พร้อมแนบ',
            photosAttached: 'รูปที่แนบ',

            // ===== Confirmation =====
            confirmRecording: 'ยืนยันการบันทึก',
            confirmRecord: 'ยืนยันและบันทึก',
            confirmUpdate: 'ยืนยันและอัปเดต',
            dateTime: 'วันที่และเวลา',
            recordedBy: 'บันทึกโดย',

            // ===== Reweight =====
            reweightWarning: 'โหลดการชั่งก่อนหน้าแล้ว การเปลี่ยนแปลงจะถูกทำเครื่องหมายเป็นการชั่งซ้ำ',
            reweightNotice: 'การดำเนินการนี้จะอัปเดตบันทึกการชั่งก่อนหน้า',
            reweightReason: 'เหตุผลในการชั่งซ้ำ',
            enterReweightReason: 'กรอกเหตุผลในการชั่งซ้ำ...',
            previousWeighingLoaded: 'โหลดการชั่งก่อนหน้าลงตะกร้าแล้ว',

            // ===== Camera =====
            camera: 'กล้อง',
            cameraNotAvailable: 'ไม่สามารถเข้าถึงกล้อง',
            startingCamera: 'กำลังเปิดกล้อง...',
            cameraError: 'กล้องมีปัญหา',
            cameraPermissionDenied: 'ไม่ได้รับอนุญาตใช้กล้อง',

            // ===== Truck Terminal =====
            truckWeights: 'น้ำหนักรถบรรทุก',
            selectOrderToRecordWeights: 'เลือกออเดอร์เพื่อบันทึกน้ำหนักรถ',
            grossRecorded: 'บันทึกน้ำหนักรวมแล้ว',
            tareRecorded: 'บันทึกน้ำหนักเปล่าแล้ว',
            netCalculated: 'คำนวณน้ำหนักสุทธิแล้ว',
            updateGross: 'แก้ไขน้ำหนักรวม',
            updateTare: 'แก้ไขน้ำหนักเปล่า',
            recordGrossWeight: 'บันทึกน้ำหนักรวม',
            recordTareWeight: 'บันทึกน้ำหนักเปล่า',
            weighTruckWithLoad: 'ชั่งรถพร้อมสินค้า',
            weighEmptyTruck: 'ชั่งรถเปล่าหลังขนถ่าย',
            saveWeight: 'บันทึกน้ำหนัก',
            truckWeightRemarks: 'หมายเหตุน้ำหนักรถ',
            weightVerification: 'ตรวจสอบน้ำหนัก',
            netTruckWeight: 'น้ำหนักสุทธิรถ',
            totalScrapWeight: 'น้ำหนักเศษวัสดุรวม',
            variance: 'ค่าต่าง',
            varianceWithinTolerance: 'ค่าต่างอยู่ในเกณฑ์',
            varianceWarning: 'คำเตือนค่าต่าง',
            varianceExceedsTolerance: 'ค่าต่างเกินเกณฑ์',
            scrapWeightRecords: 'บันทึกน้ำหนักเศษวัสดุ',
            confirmEndSession: 'คุณต้องการสิ้นสุดเซสชันนี้หรือไม่?',
            selectTruckScale: 'เลือกเครื่องชั่งรถบรรทุก',
            noTruckScalesAvailable: 'ไม่มีเครื่องชั่งรถบรรทุกที่พร้อมใช้งาน',
            notTruckScale: 'นี่ไม่ใช่เครื่องชั่งรถบรรทุก กรุณาสแกนเครื่องชั่งรถบรรทุก',
            scanScaleQRCode: 'สแกน QR เครื่องชั่ง',
            pointCameraAtScaleQR: 'เล็งกล้องไปที่ QR เครื่องชั่ง',

            // ===== Errors & Messages =====
            connectionError: 'เชื่อมต่อไม่สำเร็จ กรุณาลองใหม่',
            serverError: 'เซิร์ฟเวอร์มีปัญหา กรุณาติดต่อฝ่ายสนับสนุน',
            invalidInput: 'ข้อมูลไม่ถูกต้อง',
            requiredField: 'จำเป็นต้องกรอก',

            // ===== Validation Errors =====
            atLeastOneItemRequired: 'จำเป็นต้องมีรายการอย่างน้อยหนึ่งรายการ',
            invalidWeightValue: 'น้ำหนักไม่ถูกต้องสำหรับรายการ {item}',
            weightMustBeGreaterThanZero: 'น้ำหนักต้องมากกว่าศูนย์สำหรับรายการ {item}',
            weightExceedsScaleCapacity: 'น้ำหนัก {weight} กก. เกินกำลังการชั่งสูงสุดของเครื่องชั่ง {scale} ที่ {max} กก.',
            remarksExceedMaxLength: 'หมายเหตุเกินความยาวสูงสุด {max} ตัวอักษร',
            noActiveSession: 'ไม่พบเซสชัน POS ที่เปิดอยู่',
            sessionNotBelongToUser: 'เซสชันนี้ไม่ได้เป็นของผู้ใช้ปัจจุบัน',
            invalidOrderId: 'รหัสออเดอร์ไม่ถูกต้อง',
            orderNotFound: 'ไม่พบออเดอร์',
            orderAlreadyCompleted: 'ออเดอร์นี้เสร็จสิ้นแล้ว',
            orderAlreadyWeighed: 'ออเดอร์นี้ชั่งน้ำหนักแล้ว',
            scaleNotFound: 'ไม่พบเครื่องชั่ง: {scale}',
            photoUploadFailed: 'อัปโหลดรูปภาพไม่สำเร็จ',

            // ===== Units =====
            kg: 'กก.',
            ton: 'ตัน',

            // ===== Time =====
            today: 'วันนี้',
            yesterday: 'เมื่อวาน',
            now: 'ตอนนี้'
        }
    };

    /**
     * Initialize the translation system
     * @param {string} lang - Initial language (optional, defaults to localStorage or 'en')
     */
    function init(lang) {
        if (lang && availableLanguages.includes(lang)) {
            currentLanguage = lang;
        } else {
            // Try to get from localStorage
            const stored = localStorage.getItem('posLanguage');
            if (stored && availableLanguages.includes(stored)) {
                currentLanguage = stored;
            }
        }
        return currentLanguage;
    }

    /**
     * Get translated string
     * @param {string} key - Translation key
     * @param {object} params - Optional parameters for interpolation
     * @returns {string} Translated string or key if not found
     */
    function t(key, params) {
        let text = translations[currentLanguage][key] || translations['en'][key] || key;

        // Handle parameter interpolation
        if (params) {
            Object.keys(params).forEach(param => {
                text = text.replace(new RegExp(`{${param}}`, 'g'), params[param]);
            });
        }

        return text;
    }

    /**
     * Set current language
     * @param {string} lang - Language code ('en' or 'th')
     */
    function setLanguage(lang) {
        if (availableLanguages.includes(lang)) {
            currentLanguage = lang;
            localStorage.setItem('posLanguage', lang);
            return true;
        }
        return false;
    }

    /**
     * Get current language
     * @returns {string} Current language code
     */
    function getLanguage() {
        return currentLanguage;
    }

    /**
     * Toggle between languages
     * @returns {string} New language code
     */
    function toggleLanguage() {
        const newLang = currentLanguage === 'en' ? 'th' : 'en';
        setLanguage(newLang);
        return newLang;
    }

    /**
     * Get all available languages
     * @returns {array} Array of language codes
     */
    function getAvailableLanguages() {
        return [...availableLanguages];
    }

    /**
     * Add custom translations (for extending)
     * @param {string} lang - Language code
     * @param {object} newTranslations - Translation key-value pairs to add
     */
    function extend(lang, newTranslations) {
        if (translations[lang]) {
            Object.assign(translations[lang], newTranslations);
        }
    }

    /**
     * Get all translations for a language (useful for debugging)
     * @param {string} lang - Language code (optional, defaults to current)
     * @returns {object} Translation object
     */
    function getAll(lang) {
        return translations[lang || currentLanguage] || {};
    }

    // Public API
    return {
        init,
        t,
        setLanguage,
        getLanguage,
        toggleLanguage,
        getAvailableLanguages,
        extend,
        getAll
    };
})();

// Make it available globally
window.POS_I18N = POS_I18N;
