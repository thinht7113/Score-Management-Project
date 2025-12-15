# Admin UI Scaffold

- Single-page Bootstrap UI with sidebar.
- Calls existing APIs:
  - /api/analytics/kpi, /api/analytics/top-fails
  - /api/admin/import/curriculum|class-roster|grades (preview/commit)
  - /api/admin/users (list/create), /api/admin/users/<u>/reset-password
  - /api/admin/configs GET/PUT
  - /api/admin/warning/scan, /api/admin/warning/cases
  - /api/admin/import/logs 

## Mount
```python
from admin_ui.admin_ui import admin_ui_bp
app.register_blueprint(admin_ui_bp, url_prefix="/admin")
```

Truy cập: http://localhost:5000/admin/
