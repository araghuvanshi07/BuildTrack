DEFAULT_SUPERVISOR_PERMISSIONS = {'add_worker', 'mark_attendance'}

OPTIONAL_SUPERVISOR_PERMISSIONS = {
    'create_site',
    'create_task',
    'add_expense',
    'approve_expense',
    'view_reports',
}

ALL_SUPERVISOR_PERMISSIONS = DEFAULT_SUPERVISOR_PERMISSIONS | OPTIONAL_SUPERVISOR_PERMISSIONS
