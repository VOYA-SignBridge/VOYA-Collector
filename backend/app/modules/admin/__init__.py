"""Administrative web-system services."""

from app.modules.admin.user_service import list_users, set_user_admin_role

__all__ = ["list_users", "set_user_admin_role"]
