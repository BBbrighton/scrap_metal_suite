/**
 * Container Redesign Translations
 * Extends POS_I18N with container-specific keys for the Dropoff
 * container redesign (truck terminal + container weighing flows).
 * Must be loaded AFTER pos-translations.js.
 */
(function() {
    if (!window.POS_I18N) {
        console.error('POS_I18N not loaded. Load pos-translations.js first.');
        return;
    }

    POS_I18N.extend('en', {
        // Domain
        container: 'Container',
        new_container: 'New Container',
        edit_container: 'Edit Container',
        void_container: 'Void Container',
        weight_history: 'Weight History',
        container_type: 'Container Type',
        container_count: 'Containers',
        bag: 'Bag',
        bin: 'Bin',
        pallet: 'Pallet',
        other: 'Other',

        // Weights
        net_weight: 'Net Weight',
        gross_weight: 'Gross Weight',
        tare_weight: 'Tare Weight',
        total_weight: 'Total Weight',
        indicated_weight: 'Indicated Weight',
        grade: 'Grade',
        scale: 'Scale',

        // Inline weighing card (terminal redesign)
        select_grade_from_items: 'Select grade from item list',
        manualEntry: 'Manual',
        scaleAuto: 'Scale',
        tare: 'Tare',
        save_and_print: 'Save & Print',
        live_weight: 'Live weight',
        session: 'Session',
        operator: 'Operator',

        // Status
        status_active: 'Active',
        status_reweighed: 'Reweighed',
        status_voided: 'Voided',
        status_paused: 'Paused',
        status_in_progress: 'In Progress',
        status_completed: 'Completed',
        status_needs_review: 'Needs Review',
        status_verified: 'Verified',

        // Actions
        action_reweigh: 'Reweigh',
        action_pause: 'Pause',
        action_resume: 'Resume',
        action_complete: 'Complete',
        action_switch_scale: 'Switch Scale',
        action_reassign: 'Reassign Session',
        action_mark_verified: 'Mark Verified',
        action_override_verification: 'Override Verification',
        action_void: 'Void',
        action_scan: 'Scan',
        action_print_sticker: 'Print Sticker',
        action_print_all_stickers: 'Print All (Stickers)',
        action_reprint: 'Reprint',
        action_take_photo: 'Take Photo',
        action_reopen: 'Reopen',

        // Photos (Wave 11)
        photo_count_label: 'Photos',
        photos_attached: 'Photos attached',
        photos_attach_failed: 'Failed to attach some photos',

        // Reopen flow (Wave 11)
        prompt_reopen_reason: 'Reason to reopen this dropoff:',
        dropoff_reopened: 'Dropoff reopened',
        dropoff_reopened_cancel: 'Dropoff reopened — receipt {0} cancelled, fresh receipt will be issued on next finish',
        dropoff_completed_banner: 'Drop-off completed. Click Reopen above to add more bags.',
        journal_empty_completed: 'Drop-off closed — Reopen to add or modify bags.',
        noRecentWeight: 'No active receipt yet — finish weighing first.',

        // Verification
        override_reason: 'Override Reason',

        // Wave 10
        scrap_weight_issued: 'Receipt issued',
        scrap_weight_amended: 'Receipt amended (reweigh)',

        // Wave 11 (three-pane terminal)
        container_empty_hint: 'No containers yet — click an item to start weighing',

        // Prompts
        prompt_reweigh_reason: 'Reason for reweigh',
        prompt_pause_reason: 'Reason for pause',
        prompt_void_reason: 'Reason for voiding',
        prompt_switch_scale_reason: 'Reason for switching scale',
        prompt_reassign_reason: 'Reason for reassignment',
        prompt_override_reason: 'Reason for verification override',

        // Errors / messages
        error_locked_session: 'Dropoff is locked to a different session',
        error_scale_mismatch: 'Scale does not match dropoff lock',
        error_weight_invalid: 'Invalid weight',
        error_weight_exceeds_capacity: 'Weight exceeds scale capacity',
        error_grade_not_expected: 'Grade not in expected items',
        error_reason_required: 'Reason required',
        sticker_printed: 'Sticker printed',
        container_added: 'Container added',
        container_reweighed: 'Container reweighed',
        container_voided: 'Container voided',
        dropoff_paused: 'Dropoff paused',
        dropoff_resumed: 'Dropoff resumed',
        scale_switched: 'Scale switched',
        session_reassigned: 'Session reassigned',
    });

    POS_I18N.extend('th', {
        // Domain
        container: 'ภาชนะ',
        new_container: 'เพิ่มภาชนะ',
        edit_container: 'แก้ไขภาชนะ',
        void_container: 'ยกเลิกภาชนะ',
        weight_history: 'ประวัติการชั่ง',
        container_type: 'ประเภทภาชนะ',
        container_count: 'ภาชนะ',
        bag: 'ถุง',
        bin: 'ถัง',
        pallet: 'พาเลท',
        other: 'อื่น ๆ',

        // Weights
        net_weight: 'น้ำหนักสุทธิ',
        gross_weight: 'น้ำหนักรวม',
        tare_weight: 'น้ำหนักภาชนะ',
        total_weight: 'น้ำหนักรวมทั้งหมด',
        indicated_weight: 'น้ำหนักตามแจ้ง',
        grade: 'เกรด',

        // Inline weighing card (terminal redesign)
        select_grade_from_items: 'เลือกเกรดจากรายการสินค้า',
        manualEntry: 'ป้อนเอง',
        scaleAuto: 'ตราชั่ง',
        tare: 'ทาร์า',
        save_and_print: 'บันทึก & พิมพ์',
        live_weight: 'น้ำหนักสด',
        scale: 'ตราชั่ง',
        session: 'เซสชัน',
        operator: 'ผู้ปฏิบัติงาน',

        // Status
        status_active: 'ใช้งาน',
        status_reweighed: 'ชั่งใหม่แล้ว',
        status_voided: 'ยกเลิก',
        status_paused: 'หยุดชั่วคราว',
        status_in_progress: 'กำลังดำเนินการ',
        status_completed: 'เสร็จสิ้น',
        status_needs_review: 'ต้องตรวจสอบ',
        status_verified: 'ตรวจสอบแล้ว',

        // Actions
        action_reweigh: 'ชั่งใหม่',
        action_pause: 'หยุดชั่วคราว',
        action_resume: 'ทำงานต่อ',
        action_complete: 'เสร็จสิ้น',
        action_switch_scale: 'เปลี่ยนตราชั่ง',
        action_reassign: 'เปลี่ยนเซสชัน',
        action_mark_verified: 'ยืนยันการตรวจสอบ',
        action_override_verification: 'ข้ามการตรวจสอบ',
        action_void: 'ยกเลิก',
        action_scan: 'สแกน',
        action_print_sticker: 'พิมพ์สติ๊กเกอร์',
        action_print_all_stickers: 'พิมพ์สติ๊กเกอร์ทั้งหมด',
        action_reprint: 'พิมพ์ซ้ำ',
        action_take_photo: 'ถ่ายรูป',
        action_reopen: 'เปิดใหม่',

        // Photos (Wave 11)
        photo_count_label: 'รูป',
        photos_attached: 'แนบรูปแล้ว',
        photos_attach_failed: 'แนบรูปบางรูปล้มเหลว',

        // Reopen flow (Wave 11)
        prompt_reopen_reason: 'เหตุผลในการเปิดใบนี้ใหม่:',
        dropoff_reopened: 'เปิดใบดร็อปออฟใหม่แล้ว',
        dropoff_reopened_cancel: 'เปิดใบดร็อปออฟใหม่ — ใบชั่ง {0} ถูกยกเลิก จะออกใบใหม่เมื่อกดเสร็จสิ้นการชั่งครั้งถัดไป',
        dropoff_completed_banner: 'ใบดร็อปออฟเสร็จสิ้นแล้ว กดเปิดใหม่ด้านบนเพื่อเพิ่มถุง',
        journal_empty_completed: 'ใบดร็อปออฟปิดแล้ว กดเปิดใหม่เพื่อเพิ่มหรือแก้ไขถุง',
        noRecentWeight: 'ยังไม่มีใบชั่ง — กดเสร็จสิ้นการชั่งก่อน',

        // Verification
        override_reason: 'เหตุผลในการข้าม',

        // Wave 10
        scrap_weight_issued: 'ออกใบชั่ง',
        scrap_weight_amended: 'ออกใบชั่งฉบับแก้ไข (ชั่งซ้ำ)',

        // Wave 11 (three-pane terminal)
        container_empty_hint: 'ยังไม่มีภาชนะ — เลือกเกรดจากรายการสินค้าเพื่อเริ่มชั่ง',

        // Prompts
        prompt_reweigh_reason: 'เหตุผลในการชั่งใหม่',
        prompt_pause_reason: 'เหตุผลในการหยุด',
        prompt_void_reason: 'เหตุผลในการยกเลิก',
        prompt_switch_scale_reason: 'เหตุผลในการเปลี่ยนตราชั่ง',
        prompt_reassign_reason: 'เหตุผลในการเปลี่ยนเซสชัน',
        prompt_override_reason: 'เหตุผลในการข้ามการตรวจสอบ',

        // Errors / messages
        error_locked_session: 'ใบส่งมอบถูกล็อกกับเซสชันอื่น',
        error_scale_mismatch: 'ตราชั่งไม่ตรงกับที่ล็อก',
        error_weight_invalid: 'น้ำหนักไม่ถูกต้อง',
        error_weight_exceeds_capacity: 'น้ำหนักเกินความสามารถของตราชั่ง',
        error_grade_not_expected: 'เกรดไม่อยู่ในรายการที่คาดไว้',
        error_reason_required: 'ต้องระบุเหตุผล',
        sticker_printed: 'พิมพ์สติ๊กเกอร์แล้ว',
        container_added: 'เพิ่มภาชนะแล้ว',
        container_reweighed: 'ชั่งภาชนะใหม่แล้ว',
        container_voided: 'ยกเลิกภาชนะแล้ว',
        dropoff_paused: 'หยุดใบส่งมอบชั่วคราว',
        dropoff_resumed: 'ทำงานต่อใบส่งมอบ',
        scale_switched: 'เปลี่ยนตราชั่งแล้ว',
        session_reassigned: 'เปลี่ยนเซสชันแล้ว',
    });
})();
