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
            posTitle: 'SMT Price LockS by X-DESK',
            activeSession: 'Active Session',
            noActiveSession: 'No Active Session',
            selectTerminal: 'Select a terminal to start a new session',
            scrapWeighing: 'Scrap Weighing',
            scrapWeighingDesc: 'Record scrap weights by item',
            truckScale: 'Truck Scale',
            truckScaleDesc: 'Record gross/tare truck weights',
            productionSortingDesc: 'QA/QC sorting and verification',
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

            // ===== Scale Connection =====
            scaleConnection: 'Scale Connection',
            connectingToScale: 'Connecting to scale...',
            scaleConnectedSuccess: 'Scale connected successfully!',
            scaleConnectionFailed: 'Could not connect to scale',
            scaleNotConfigured: 'Scale serial settings not configured.',
            scaleReconfigureHint: 'The scale may need to be reconfigured. Use the Scale Test page to auto-detect settings.',
            noPortSelected: 'No serial port selected',
            noDataFromScale: 'No valid data received from scale',
            protocol: 'Protocol:',
            currentWeight: 'Current Weight:',
            tryAgain: 'Try Again',
            reconfigureScale: 'Reconfigure Scale',
            continue: 'Continue',
            webSerialNotSupported: 'WebSerial API not supported. Please use Chrome or Edge browser.',
            unknownError: 'Unknown error occurred',
            useManualEntry: 'Use Manual Entry',
            confirmScaleManual: 'Confirm Scale (Manual Entry)',
            scaleSetManualMode: 'Scale set - using manual weight entry',

            // ===== Live Weight =====
            readingFromScale: 'Reading from scale',
            useThisWeight: 'Use This Weight',
            enterManually: 'Enter Manually',
            useScaleReading: 'Use Scale Reading',
            stable: 'Stable',
            measuring: 'Measuring...',
            scaleReconnected: 'Scale reconnected',
            selectPortToReconnect: 'Please select the scale port to reconnect',
            scaleDisconnected: 'Scale disconnected',
            scaleUnplugged: 'Scale disconnected. Reconnect or replug USB.',
            connected: 'Connected',
            disconnected: 'Disconnected',
            reconnect: 'Reconnect',
            disconnect: 'Disconnect',

            // ===== Drop-off =====
            dropoffId: 'Drop-off ID',
            dropoff: 'Drop-off',
            dropoffs: 'Drop-offs',
            dropoffDate: 'Drop-off Date',
            dropoffItems: 'Drop-off Items',
            indicatedWeight: 'Indicated Weight',
            noDropoffItems: 'No items in this drop-off',
            expectedItems: 'Expected Items',
            dropoffNotFound: 'Drop-off not found',
            noDropoffsFound: 'No drop-offs found',
            errorSearchingDropoff: 'Error searching for drop-off',
            scanDropoffBarcode: 'Scan Drop-off Barcode/QR',
            pointCamera: 'Point camera at barcode or QR code',
            orEnterManually: 'Or enter manually:',
            enterDropoffId: 'Enter Drop-off ID or scan...',
            scan: 'Scan',

            // ===== Orders (legacy) =====
            orderId: 'Order ID',
            order: 'Order',
            orders: 'Orders',
            orderDate: 'Order Date',
            orderItems: 'Order Items',
            noOrderItems: 'No items in this order',
            orderNotFound: 'Order not found',
            noOrdersFound: 'No orders found',
            errorSearching: 'Error searching for order',
            scanOrderBarcode: 'Scan order barcode/QR',
            enterOrderId: 'Enter order ID or scan...',

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
            enterValidWeight: 'Please enter a valid weight greater than 0',
            noDropoffSelected: 'Please select a dropoff first',
            failedToRecordWeight: 'Failed to record weight',
            failedToRecord: 'Failed to record weight',
            grossWeight: 'Gross Weight',
            tareWeight: 'Tare Weight',
            netWeight: 'Net Weight',
            recordGross: 'Record Gross',
            recordTare: 'Record Tare',
            truckGrossWeight: 'Truck Weight (Gross)',

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
            addAnother: 'Add & Take Another',
            photoReady: 'Photo captured and ready to attach',
            photoAdded: 'Photo added',
            photosReady: 'photos ready to attach',
            photosAttached: 'photo(s) attached',

            // ===== CCTV =====
            cctv: 'CCTV',
            cctvCapture: 'Capture from CCTV',
            cctvConnecting: 'Connecting to camera...',
            cctvOffline: 'Camera offline',
            cctvCaptured: 'CCTV photo captured',
            cctvAgentOffline: 'Capture agent offline - weight saved without photos',
            noTruckCameras: 'No truck cameras configured',
            selectCamera: 'Select Camera',
            saveWeightFirst: 'Save the weight first',

            // ===== Camera Test / Status Page =====
            cameraTestTitle: 'Camera Configuration',
            cameraTestSubtitle: 'Verify the CCTV cameras are reachable and capturing',
            transport: 'Transport',
            transportAgent: 'Local capture agent',
            transportBackend: 'Server-side fetch',
            transportAgentHelp: 'The on-site agent fetches from the camera LAN and uploads to the server.',
            transportBackendHelp: 'This server fetches the cameras directly. Only works when the server is on the camera LAN.',
            agentStatus: 'Agent Status',
            agentOnline: 'Agent online',
            agentOffline: 'Agent unreachable',
            cloudStatus: 'Server reachable',
            clockSyncStatus: 'Camera clocks',
            pendingUploads: 'Pending uploads',
            camerasTitle: 'Cameras',
            testAll: 'Test All',
            testConnection: 'Test',
            livePreview: 'Preview',
            stopPreview: 'Stop',
            online: 'Online',
            offline: 'Offline',
            notTested: 'Not tested',
            testing: 'Testing...',
            channelLabel: 'Channel',
            resolution: 'Resolution',
            ipAddress: 'IP Address',
            noCamerasConfigured: 'No cameras configured. Add one in Desk → Camera.',
            activityLog: 'Activity Log',
            clearLog: 'Clear',
            cameraStatusAll: 'All cameras online',
            cameraStatusSome: 'Some cameras offline',
            cameraStatusNone: 'No cameras reachable',
            testCameras: 'Test Cameras',
            refresh: 'Refresh',
            containers: 'Containers',
            noContainersFound: 'No containers found',
            alreadySorted: 'sorting started',
            sortingContainer: 'Sorting',
            selectContainerFirst: 'Select a container first — pick one from the list on the left.',


            // ===== Post-weigh photo review =====
            weightRecorded: 'Weight Recorded',
            capturingPhotos: 'Capturing photos from the cameras...',
            photosCaptured: 'photo(s) captured',
            noPhotosCaptured: 'No photos captured',
            someCamerasFailed: 'some cameras did not respond',
            confirmAndPrint: 'Confirm & Print',
            recaptureWeight: 'Recapture Weight',
            recaptureWeightHint: 'Enter the weight again to reweigh. A reweigh reason will be required.',

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
            zoom: 'Zoom',
            tilt: 'Tilt',
            optical: 'Optical',
            digital: 'Digital',

            // ===== Truck Terminal =====
            truckWeights: 'Truck Weights',
            selectDropoffToRecordWeights: 'Select a drop-off to record truck weights',
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
            captureWeight: 'Capture Weight',
            saveWeight: 'Save Weight',
            connectScale: 'Connect Scale',
            scaleNotConnected: 'Scale not connected',
            truckWeightRemarks: 'Truck Weight Remarks',
            weightVerification: 'Weight Verification',
            threshold: 'Threshold',
            netTruckWeight: 'Net Truck Weight',
            totalScrapWeight: 'Total Scrap Weight',
            variance: 'Variance',
            varianceWithinTolerance: 'Variance within tolerance',
            varianceWarning: 'Variance warning',
            varianceExceedsTolerance: 'Variance exceeds tolerance',
            scrapWeightRecords: 'Scrap Weight Records',
            complete: 'Complete',
            completeDropoff: 'Complete Dropoff',
            confirmEndSession: 'Are you sure you want to end this session?',
            selectTruckScale: 'Select Truck Scale',
            noTruckScalesAvailable: 'No truck scales available',
            notTruckScale: 'This is not a truck scale. Please scan a truck scale.',
            scanScaleQRCode: 'Scan Scale QR Code',
            pointCameraAtScaleQR: 'Point camera at scale QR code',

            // ===== Variance (Phase 8B) =====
            truckVarianceTitle: 'Truck Variance (Net vs Scrap)',
            indicatedVarianceTitle: 'Indicated Variance (Supplier vs Actual)',
            truckVariance: 'Truck Variance',
            indicatedVariance: 'Indicated Variance',
            totalActualWeight: 'Total Actual Weight',

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
            now: 'Now',            
            // ===== Production Sorting =====
            productionSorting: 'Production Sorting',
            startProductionSession: 'Start Production Session',
            scanScaleOrSelect: 'Scan a scale QR code or select from list',
            selectDropoff: 'Select Dropoff',
            enterDropoffId: 'Enter Dropoff ID...',
            dropoffId: 'Dropoff ID:',
            supplier: 'Supplier:',
            totalWeight: 'Total Weight:',
            clearDropoff: 'Clear',
            weighItems: 'Weigh Items',
            goodItems: 'Good Items (Keep & Pay)',
            unwantedItems: 'Unwanted Items (Return)',
            selectItem: 'Select Item:',
            chooseItem: '-- Choose Item --',
            returnReason: 'Return Reason:',
            contamination: 'Contamination',
            wrongMaterial: 'Wrong Material',
            packaging: 'Packaging',
            dirtDebris: 'Dirt/Debris',
            other: 'Other',
            remarksOptional: 'Remarks (Optional):',
            notes: 'Notes...',
            captureWeight: 'Capture Weight',
            addItem: 'Add Item',
            currentSorting: 'Current Sorting',
            goodTotal: 'Good Items:',
            unwantedTotal: 'Unwanted:',
            totalSorted: 'Total Sorted:',
            variance: 'Variance:',
            submitSorting: 'Submit Sorting',
            sessionStarted: 'Session started',
            failedToStartSession: 'Failed to start session',
            confirmCloseSession: 'Are you sure you want to close this session?',
            sessionClosed: 'Session closed successfully',
            connected: 'Connected',
            disconnected: 'Disconnected',
            scaleConnected: 'Scale connected',
            scaleDisconnected: 'Scale disconnected',
            enterManually: 'Enter Manually',
            useScale: 'Use Scale',
            noItemSelected: 'No item selected',
            selectItemAndWeight: 'Please select an item and capture weight',
            noDropoffsFound: 'No dropoffs found',
            noItemsAdded: 'No items added yet',
            selectDropoffFirst: 'Please select a Dropoff first',
            addAtLeastOneItem: 'Please add at least one item',
            confirmSubmitSorting: 'Submit sorting for',
            sortingSubmitted: 'Sorting submitted:',
            error: 'Error',
            connect: 'Connect',
            disconnect: 'Disconnect',
            reconnect: 'Reconnect',
            closeSession: 'Close Session',
            startSession: 'Start Session',
            noSession: 'No Session'
        },

        th: {
            // ===== Landing Page =====
            posTitle: 'SMT Price LockS โดย X-DESK',
            activeSession: 'เซสชันที่ใช้งาน',
            noActiveSession: 'ไม่มีเซสชันที่ใช้งาน',
            selectTerminal: 'เลือกเทอร์มินัลเพื่อเริ่มเซสชันใหม่',
            scrapWeighing: 'ชั่งเศษวัสดุ',
            scrapWeighingDesc: 'บันทึกน้ำหนักเศษวัสดุตามรายการ',
            truckScale: 'เครื่องชั่งรถบรรทุก',
            truckScaleDesc: 'บันทึกน้ำหนักรวม/น้ำหนักเปล่ารถ',
            productionSortingDesc: 'การคัดแยกและตรวจสอบคุณภาพ',
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

            // ===== Scale Connection =====
            scaleConnection: 'การเชื่อมต่อเครื่องชั่ง',
            connectingToScale: 'กำลังเชื่อมต่อเครื่องชั่ง...',
            scaleConnectedSuccess: 'เชื่อมต่อเครื่องชั่งสำเร็จ!',
            scaleConnectionFailed: 'ไม่สามารถเชื่อมต่อเครื่องชั่งได้',
            scaleNotConfigured: 'ยังไม่ได้ตั้งค่าการเชื่อมต่อเครื่องชั่ง',
            scaleReconfigureHint: 'อาจต้องตั้งค่าเครื่องชั่งใหม่ ใช้หน้าทดสอบเครื่องชั่งเพื่อตรวจจับอัตโนมัติ',
            noPortSelected: 'ไม่ได้เลือกพอร์ตซีเรียล',
            noDataFromScale: 'ไม่ได้รับข้อมูลจากเครื่องชั่ง',
            protocol: 'โปรโตคอล:',
            currentWeight: 'น้ำหนักปัจจุบัน:',
            tryAgain: 'ลองใหม่',
            reconfigureScale: 'ตั้งค่าเครื่องชั่งใหม่',
            continue: 'ดำเนินการต่อ',
            webSerialNotSupported: 'เบราว์เซอร์ไม่รองรับ WebSerial กรุณาใช้ Chrome หรือ Edge',
            unknownError: 'เกิดข้อผิดพลาดที่ไม่ทราบสาเหตุ',
            useManualEntry: 'ใช้การกรอกเอง',
            confirmScaleManual: 'ยืนยันเครื่องชั่ง (กรอกเอง)',
            scaleSetManualMode: 'ตั้งค่าเครื่องชั่งแล้ว - ใช้การกรอกน้ำหนักเอง',

            // ===== Live Weight =====
            readingFromScale: 'กำลังอ่านจากเครื่องชั่ง',
            useThisWeight: 'ใช้น้ำหนักนี้',
            enterManually: 'กรอกเอง',
            useScaleReading: 'ใช้ค่าจากเครื่องชั่ง',
            stable: 'คงที่',
            measuring: 'กำลังวัด...',
            scaleReconnected: 'เครื่องชั่งเชื่อมต่อใหม่',
            selectPortToReconnect: 'กรุณาเลือกพอร์ตเครื่องชั่งเพื่อเชื่อมต่อใหม่',
            scaleDisconnected: 'เครื่องชั่งถูกตัดการเชื่อมต่อ',
            scaleUnplugged: 'เครื่องชั่งหลุด กรุณาเชื่อมต่อใหม่หรือเสียบ USB อีกครั้ง',
            connected: 'เชื่อมต่อแล้ว',
            disconnected: 'ไม่ได้เชื่อมต่อ',
            reconnect: 'เชื่อมต่อใหม่',
            disconnect: 'ตัดการเชื่อมต่อ',

            // ===== Drop-off =====
            dropoffId: 'รหัสใบส่งของ',
            dropoff: 'ใบส่งของ',
            dropoffs: 'ใบส่งของ',
            dropoffDate: 'วันที่ส่งมอบ',
            dropoffItems: 'รายการในใบส่งของ',
            indicatedWeight: 'น้ำหนักที่แจ้ง',
            noDropoffItems: 'ไม่มีรายการในใบส่งของนี้',
            expectedItems: 'รายการที่คาดหวัง',
            dropoffNotFound: 'ไม่พบใบส่งของ',
            noDropoffsFound: 'ไม่พบใบส่งของ',
            errorSearchingDropoff: 'เกิดข้อผิดพลาดในการค้นหาใบส่งของ',
            scanDropoffBarcode: 'สแกนบาร์โค้ด/QR ใบส่งของ',
            pointCamera: 'เล็งกล้องไปที่บาร์โค้ดหรือ QR โค้ด',
            orEnterManually: 'หรือกรอกเอง:',
            enterDropoffId: 'กรอกรหัสใบส่งของหรือสแกน...',
            scan: 'สแกน',

            // ===== Orders (legacy) =====
            orderId: 'รหัสออเดอร์',
            order: 'ออเดอร์',
            orders: 'ออเดอร์',
            orderDate: 'วันที่สั่ง',
            orderItems: 'รายการสินค้า',
            noOrderItems: 'ไม่มีรายการในออเดอร์นี้',
            orderNotFound: 'ไม่พบออเดอร์',
            noOrdersFound: 'ไม่พบออเดอร์',
            errorSearching: 'เกิดข้อผิดพลาดในการค้นหา',
            scanOrderBarcode: 'สแกนบาร์โค้ด/QR ออเดอร์',
            enterOrderId: 'กรอกรหัสออเดอร์หรือสแกน...',

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
            enterValidWeight: 'กรุณากรอกน้ำหนักที่ถูกต้องมากกว่า 0',
            noDropoffSelected: 'กรุณาเลือกใบส่งของก่อน',
            failedToRecordWeight: 'ไม่สามารถบันทึกน้ำหนักได้',
            failedToRecord: 'ไม่สามารถบันทึกน้ำหนักได้',
            grossWeight: 'น้ำหนักรวม',
            tareWeight: 'น้ำหนักเปล่า',
            netWeight: 'น้ำหนักสุทธิ',
            recordGross: 'บันทึกน้ำหนักรวม',
            recordTare: 'บันทึกน้ำหนักเปล่า',
            truckGrossWeight: 'น้ำหนักรถ (ขาเข้า)',

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
            addAnother: 'เพิ่มและถ่ายต่อ',
            photoReady: 'ถ่ายรูปแล้ว พร้อมแนบ',
            photoAdded: 'เพิ่มรูปแล้ว',
            photosReady: 'รูปพร้อมแนบ',
            photosAttached: 'รูปที่แนบ',

            // ===== CCTV =====
            cctv: 'กล้องวงจรปิด',
            cctvCapture: 'ถ่ายจากกล้องวงจรปิด',
            cctvConnecting: 'กำลังเชื่อมต่อกล้อง...',
            cctvOffline: 'กล้องออฟไลน์',
            cctvCaptured: 'ถ่ายรูปจากกล้องวงจรปิดแล้ว',
            cctvAgentOffline: 'ตัวเชื่อมต่อกล้องออฟไลน์ - บันทึกน้ำหนักแล้วแต่ไม่มีรูป',
            noTruckCameras: 'ยังไม่ได้ตั้งค่ากล้องรถบรรทุก',
            selectCamera: 'เลือกกล้อง',
            saveWeightFirst: 'กรุณาบันทึกน้ำหนักก่อน',

            // ===== Camera Test / Status Page =====
            cameraTestTitle: 'ตั้งค่ากล้องวงจรปิด',
            cameraTestSubtitle: 'ตรวจสอบว่ากล้องวงจรปิดเชื่อมต่อและถ่ายภาพได้',
            transport: 'ช่องทางเชื่อมต่อ',
            transportAgent: 'ตัวเชื่อมต่อในพื้นที่',
            transportBackend: 'ดึงภาพจากเซิร์ฟเวอร์',
            transportAgentHelp: 'ตัวเชื่อมต่อในพื้นที่ดึงภาพจากเครือข่ายกล้องแล้วส่งขึ้นเซิร์ฟเวอร์',
            transportBackendHelp: 'เซิร์ฟเวอร์ดึงภาพจากกล้องโดยตรง ใช้ได้เมื่อเซิร์ฟเวอร์อยู่ในเครือข่ายกล้องเท่านั้น',
            agentStatus: 'สถานะตัวเชื่อมต่อ',
            agentOnline: 'ตัวเชื่อมต่อออนไลน์',
            agentOffline: 'ไม่พบตัวเชื่อมต่อ',
            cloudStatus: 'เชื่อมต่อเซิร์ฟเวอร์ได้',
            clockSyncStatus: 'เวลาของกล้อง',
            pendingUploads: 'รออัปโหลด',
            camerasTitle: 'กล้อง',
            testAll: 'ทดสอบทั้งหมด',
            testConnection: 'ทดสอบ',
            livePreview: 'ดูภาพสด',
            stopPreview: 'หยุด',
            online: 'ออนไลน์',
            offline: 'ออฟไลน์',
            notTested: 'ยังไม่ทดสอบ',
            testing: 'กำลังทดสอบ...',
            channelLabel: 'ช่องสัญญาณ',
            resolution: 'ความละเอียด',
            ipAddress: 'ที่อยู่ IP',
            noCamerasConfigured: 'ยังไม่ได้ตั้งค่ากล้อง เพิ่มได้ที่ Desk → Camera',
            activityLog: 'บันทึกการทำงาน',
            clearLog: 'ล้าง',
            cameraStatusAll: 'กล้องออนไลน์ทั้งหมด',
            cameraStatusSome: 'กล้องบางตัวออฟไลน์',
            cameraStatusNone: 'ไม่พบกล้องที่เชื่อมต่อได้',
            testCameras: 'ทดสอบกล้อง',
            refresh: 'รีเฟรช',
            containers: 'ถุงบรรจุ',
            noContainersFound: 'ไม่พบถุงบรรจุ',
            alreadySorted: 'เริ่มคัดแยกแล้ว',
            sortingContainer: 'กำลังคัดแยก',
            selectContainerFirst: 'กรุณาเลือกถุงบรรจุก่อน — เลือกจากรายการทางซ้าย',


            // ===== Post-weigh photo review =====
            weightRecorded: 'บันทึกน้ำหนักแล้ว',
            capturingPhotos: 'กำลังถ่ายภาพจากกล้อง...',
            photosCaptured: 'ภาพที่ถ่ายได้',
            noPhotosCaptured: 'ไม่มีภาพที่ถ่ายได้',
            someCamerasFailed: 'กล้องบางตัวไม่ตอบสนอง',
            confirmAndPrint: 'ยืนยันและพิมพ์',
            recaptureWeight: 'ชั่งน้ำหนักใหม่',
            recaptureWeightHint: 'กรอกน้ำหนักอีกครั้งเพื่อชั่งใหม่ ต้องระบุเหตุผลในการชั่งใหม่',

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
            zoom: 'ซูม',
            tilt: 'เอียง',
            optical: 'ออปติคัล',
            digital: 'ดิจิทัล',

            // ===== Truck Terminal =====
            truckWeights: 'น้ำหนักรถบรรทุก',
            selectDropoffToRecordWeights: 'เลือกใบส่งของเพื่อบันทึกน้ำหนักรถ',
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
            captureWeight: 'จับค่าน้ำหนัก',
            saveWeight: 'บันทึกน้ำหนัก',
            connectScale: 'เชื่อมต่อเครื่องชั่ง',
            scaleNotConnected: 'ยังไม่เชื่อมต่อเครื่องชั่ง',
            truckWeightRemarks: 'หมายเหตุน้ำหนักรถ',
            weightVerification: 'ตรวจสอบน้ำหนัก',
            threshold: 'เกณฑ์',
            netTruckWeight: 'น้ำหนักสุทธิรถ',
            totalScrapWeight: 'น้ำหนักเศษวัสดุรวม',
            variance: 'ค่าต่าง',
            varianceWithinTolerance: 'ค่าต่างอยู่ในเกณฑ์',
            varianceWarning: 'คำเตือนค่าต่าง',
            varianceExceedsTolerance: 'ค่าต่างเกินเกณฑ์',
            scrapWeightRecords: 'บันทึกน้ำหนักเศษวัสดุ',
            complete: 'เสร็จสิ้น',
            completeDropoff: 'เสร็จสิ้นใบส่งของ',
            confirmEndSession: 'คุณต้องการสิ้นสุดเซสชันนี้หรือไม่?',
            selectTruckScale: 'เลือกเครื่องชั่งรถบรรทุก',
            noTruckScalesAvailable: 'ไม่มีเครื่องชั่งรถบรรทุกที่พร้อมใช้งาน',
            notTruckScale: 'นี่ไม่ใช่เครื่องชั่งรถบรรทุก กรุณาสแกนเครื่องชั่งรถบรรทุก',
            scanScaleQRCode: 'สแกน QR เครื่องชั่ง',
            pointCameraAtScaleQR: 'เล็งกล้องไปที่ QR เครื่องชั่ง',

            // ===== Variance (Phase 8B) =====
            truckVarianceTitle: 'ค่าต่างรถ (สุทธิ vs เศษวัสดุ)',
            indicatedVarianceTitle: 'ค่าต่างแจ้ง (ผู้ขาย vs จริง)',
            truckVariance: 'ค่าต่างรถ',
            indicatedVariance: 'ค่าต่างแจ้ง',
            totalActualWeight: 'น้ำหนักจริงรวม',

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
            now: 'ตอนนี้',
            
            // ===== Production Sorting =====
            productionSorting: 'การคัดแยกสินค้า',
            startProductionSession: 'เริ่มเซสชันการคัดแยก',
            scanScaleOrSelect: 'สแกน QR ของตาชั่ง หรือเลือกจากรายการ',
            selectDropoff: 'เลือกรอบรับสินค้า',
            enterDropoffId: 'กรอก ID รอบรับสินค้า...',
            dropoffId: 'รหัสรอบรับ:',
            supplier: 'ผู้ขาย:',
            totalWeight: 'น้ำหนักรวม:',
            clearDropoff: 'ล้าง',
            weighItems: 'ชั่งน้ำหนักสินค้า',
            goodItems: 'สินค้าดี (รับซื้อ)',
            unwantedItems: 'ของที่ไม่ต้องการ (คืนให้)',
            selectItem: 'เลือกสินค้า:',
            chooseItem: '-- เลือกสินค้า --',
            returnReason: 'เหตุผลการคืน:',
            contamination: 'ปนเปื้อน',
            wrongMaterial: 'วัตถุดิบไม่ถูกต้อง',
            packaging: 'บรรจุภัณฑ์',
            dirtDebris: 'ดิน/เศษขยะ',
            other: 'อื่นๆ',
            remarksOptional: 'หมายเหตุ (ถ้ามี):',
            notes: 'บันทึก...',
            captureWeight: 'บันทึกน้ำหนัก',
            addItem: 'เพิ่มสินค้า',
            currentSorting: 'การคัดแยกปัจจุบัน',
            goodTotal: 'สินค้าดี:',
            unwantedTotal: 'ของไม่ต้องการ:',
            totalSorted: 'น้ำหนักรวมที่คัดแยก:',
            variance: 'ส่วนต่าง:',
            submitSorting: 'บันทึกการคัดแยก',
            sessionStarted: 'เริ่มเซสชันแล้ว',
            failedToStartSession: 'ไม่สามารถเริ่มเซสชันได้',
            confirmCloseSession: 'คุณแน่ใจหรือไม่ที่จะปิดเซสชันนี้?',
            sessionClosed: 'ปิดเซสชันสำเร็จ',
            connected: 'เชื่อมต่อแล้ว',
            disconnected: 'ไม่ได้เชื่อมต่อ',
            scaleConnected: 'เชื่อมต่อตาชั่งแล้ว',
            scaleDisconnected: 'ตาชั่งถูกตัดการเชื่อมต่อ',
            enterManually: 'กรอกด้วยตนเอง',
            useScale: 'ใช้ตาชั่ง',
            noItemSelected: 'ยังไม่ได้เลือกสินค้า',
            selectItemAndWeight: 'กรุณาเลือกสินค้าและบันทึกน้ำหนัก',
            noDropoffsFound: 'ไม่พบรอบรับสินค้า',
            noItemsAdded: 'ยังไม่มีสินค้า',
            selectDropoffFirst: 'กรุณาเลือกรอบรับสินค้าก่อน',
            addAtLeastOneItem: 'กรุณาเพิ่มสินค้าอย่างน้อย 1 รายการ',
            confirmSubmitSorting: 'บันทึกการคัดแยกสำหรับ',
            sortingSubmitted: 'บันทึกการคัดแยกแล้ว:',
            error: 'ข้อผิดพลาด',
            connect: 'เชื่อมต่อ',
            disconnect: 'ตัดการเชื่อมต่อ',
            reconnect: 'เชื่อมต่อใหม่',
            closeSession: 'ปิดเซสชัน',
            startSession: 'เริ่มเซสชัน',
            noSession: 'ไม่มีเซสชัน'
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
