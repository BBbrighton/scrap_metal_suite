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
        container_no: 'Container No',
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
        action_approve_deviation: 'Approve Deviation',
        action_mark_verified: 'Mark Verified',
        action_override_verification: 'Override Verification',
        action_void: 'Void',
        action_scan: 'Scan',
        action_print_thermal: 'Print Thermal',
        action_print_sticker: 'Print Sticker',
        action_print_all_thermal: 'Print All (Thermal)',
        action_print_all_stickers: 'Print All (Stickers)',
        action_reprint: 'Reprint',

        // Deviations
        deviation: 'Deviation',
        deviation_warning: 'Grade differs from expected',
        downgrade: 'Downgrade',
        upgrade: 'Upgrade',
        substitution: 'Substitution',
        unplanned_add: 'Unplanned-Add',
        deviation_approval_required: 'Approval Required',
        deviation_approved_by: 'Approved by',
        override_reason: 'Override Reason',

        // Prompts
        prompt_deviation_reason: 'Reason for deviation',
        prompt_deviation_type: 'Deviation type',
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
        container_no: 'ภาชนะที่',
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
        action_approve_deviation: 'อนุมัติความเบี่ยงเบน',
        action_mark_verified: 'ยืนยันการตรวจสอบ',
        action_override_verification: 'ข้ามการตรวจสอบ',
        action_void: 'ยกเลิก',
        action_scan: 'สแกน',
        action_print_thermal: 'พิมพ์ใบรับ',
        action_print_sticker: 'พิมพ์สติ๊กเกอร์',
        action_print_all_thermal: 'พิมพ์ใบรับทั้งหมด',
        action_print_all_stickers: 'พิมพ์สติ๊กเกอร์ทั้งหมด',
        action_reprint: 'พิมพ์ซ้ำ',

        // Deviations
        deviation: 'ความเบี่ยงเบน',
        deviation_warning: 'เกรดต่างจากที่คาดไว้',
        downgrade: 'ลดเกรด',
        upgrade: 'เพิ่มเกรด',
        substitution: 'ทดแทน',
        unplanned_add: 'เพิ่มนอกแผน',
        deviation_approval_required: 'ต้องขออนุมัติ',
        deviation_approved_by: 'อนุมัติโดย',
        override_reason: 'เหตุผลในการข้าม',

        // Prompts
        prompt_deviation_reason: 'เหตุผลของความเบี่ยงเบน',
        prompt_deviation_type: 'ประเภทความเบี่ยงเบน',
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
