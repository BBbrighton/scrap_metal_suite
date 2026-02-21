/**
 * Production Sorting Translations
 * Extends POS_I18N with production-specific keys.
 * Must be loaded AFTER pos-translations.js.
 */
(function() {
    if (!window.POS_I18N) {
        console.error('POS_I18N not loaded. Load pos-translations.js first.');
        return;
    }

    POS_I18N.extend('en', {
        // Landing
        productionTitle: 'Production Sorting by X-DESK',
        sortingTerminal: 'Sorting Terminal',
        sortingTerminalDesc: 'Sort, grade, and verify delivered materials',
        startSorting: 'Start Sorting',
        resumeSession: 'Resume Session',
        noActiveSession: 'No active session',

        // Source Items
        sourceItems: 'Source Items (from Dropoff)',
        sortedItems: 'Sorted Items',
        itemGroup: 'Item Group',
        allGroups: 'All',

        // Dropoff Lookup
        searchDropoff: 'Search completed drop-off...',
        noDropoffsFound: 'No completed drop-offs found',
        dropoffAlreadySorted: 'This drop-off already has a sorting record',
        loadExisting: 'Load existing sorting',
        dropoffRef: 'Dropoff',
        supplierLabel: 'Supplier',
        plateLabel: 'Plate',
        dropoffWeight: 'Dropoff Weight',

        // Variance
        totalSorted: 'Total Sorted',
        varianceAmount: 'Variance',
        variancePercent: 'Variance %',
        varianceThreshold: 'Threshold',
        withinThreshold: 'Within threshold',
        exceedsThreshold: 'Exceeds threshold — manager approval required',
        verificationLabel: 'Verification',
        verified: 'Verified',
        needsReview: 'Needs Review',
        pendingVerification: 'Pending',

        // Actions
        saveSorting: 'Save',
        completeSorting: 'Complete',
        confirmComplete: 'Confirm Completion',
        sortingSaved: 'Sorting saved',
        sortingCompleted: 'Sorting completed',
        printReport: 'Print',
        selectItem: 'Select an item from the grid',
        enterWeight: 'Enter Weight',
        noDropoffSelected: 'Search or scan a dropoff first',

        // Session
        productionSession: 'Production Session',
        totalSortings: 'Sortings',
        totalWeightSorted: 'Weight Sorted',
        closeSession: 'Close Session',
        confirmCloseSession: 'Close this session?',
        sessionClosed: 'Session closed',
        sessionSummary: 'Session Summary',

        // Scale
        selectScale: 'Select Scale',
        noScaleSet: 'No scale',
        scaleConnected: 'Connected',
        scaleDisconnected: 'Disconnected',
        connectScale: 'Connect Scale',
        liveWeight: 'Live',
        manualWeight: 'Manual',

        // Manager Override
        managerApprovalRequired: 'Manager approval required',
        managerOverride: 'Manager Override',
    });

    POS_I18N.extend('th', {
        // Landing
        productionTitle: 'คัดแยกวัตถุดิบ โดย X-DESK',
        sortingTerminal: 'เทอร์มินัลคัดแยก',
        sortingTerminalDesc: 'คัดแยก จัดเกรด และตรวจสอบวัตถุดิบ',
        startSorting: 'เริ่มคัดแยก',
        resumeSession: 'กลับเข้าเซสชัน',
        noActiveSession: 'ไม่มีเซสชันที่เปิดอยู่',

        // Source Items
        sourceItems: 'รายการต้นทาง (จากใบส่งของ)',
        sortedItems: 'รายการที่คัดแยก',
        itemGroup: 'กลุ่มสินค้า',
        allGroups: 'ทั้งหมด',

        // Dropoff Lookup
        searchDropoff: 'ค้นหาใบส่งของ...',
        noDropoffsFound: 'ไม่พบใบส่งของ',
        dropoffAlreadySorted: 'ใบส่งของนี้มีบันทึกคัดแยกแล้ว',
        loadExisting: 'โหลดการคัดแยกที่มีอยู่',
        dropoffRef: 'ใบส่งของ',
        supplierLabel: 'ผู้จำหน่าย',
        plateLabel: 'ทะเบียนรถ',
        dropoffWeight: 'น้ำหนักใบส่งของ',

        // Variance
        totalSorted: 'น้ำหนักคัดแยกรวม',
        varianceAmount: 'ค่าต่าง',
        variancePercent: 'ค่าต่าง %',
        varianceThreshold: 'เกณฑ์',
        withinThreshold: 'อยู่ในเกณฑ์',
        exceedsThreshold: 'เกินเกณฑ์ — ต้องได้รับอนุมัติจากผู้จัดการ',
        verificationLabel: 'การตรวจสอบ',
        verified: 'ตรวจสอบแล้ว',
        needsReview: 'ต้องตรวจสอบ',
        pendingVerification: 'รอดำเนินการ',

        // Actions
        saveSorting: 'บันทึก',
        completeSorting: 'เสร็จสิ้น',
        confirmComplete: 'ยืนยันการเสร็จสิ้น',
        sortingSaved: 'บันทึกสำเร็จ',
        sortingCompleted: 'คัดแยกเสร็จสิ้น',
        printReport: 'พิมพ์',
        selectItem: 'เลือกรายการจากตาราง',
        enterWeight: 'ใส่น้ำหนัก',
        noDropoffSelected: 'ค้นหาหรือสแกนใบส่งของก่อน',

        // Session
        productionSession: 'เซสชันคัดแยก',
        totalSortings: 'จำนวนคัดแยก',
        totalWeightSorted: 'น้ำหนักรวม',
        closeSession: 'ปิดเซสชัน',
        confirmCloseSession: 'ปิดเซสชันนี้?',
        sessionClosed: 'ปิดเซสชันแล้ว',
        sessionSummary: 'สรุปเซสชัน',

        // Scale
        selectScale: 'เลือกตาชั่ง',
        noScaleSet: 'ไม่มีตาชั่ง',
        scaleConnected: 'เชื่อมต่อแล้ว',
        scaleDisconnected: 'ไม่ได้เชื่อมต่อ',
        connectScale: 'เชื่อมต่อตาชั่ง',
        liveWeight: 'อัตโนมัติ',
        manualWeight: 'ใส่เอง',

        // Manager Override
        managerApprovalRequired: 'ต้องได้รับอนุมัติจากผู้จัดการ',
        managerOverride: 'ผู้จัดการอนุมัติ',
    });
})();
