def test_admin_data_routes_keep_paths_and_legacy_exports():
    from app.routers import admin, admin_data

    assert admin.get_data_report is admin_data.get_data_report
    assert admin.sync_local_files is admin_data.sync_local_files
    assert admin.get_sync_status is admin_data.get_sync_status

    routes = {route.path: route.endpoint for route in admin.router.routes}
    assert routes["/admin/data-report"] is admin_data.get_data_report
    assert routes["/admin/sync-local"] is admin_data.sync_local_files
    assert routes["/admin/sync-status/{task_id}"] is admin_data.get_sync_status


def test_admin_data_routes_are_registered_once():
    from app.routers import admin

    paths = [route.path for route in admin.router.routes]
    assert paths.count("/admin/data-report") == 1
    assert paths.count("/admin/sync-local") == 1
    assert paths.count("/admin/sync-status/{task_id}") == 1
