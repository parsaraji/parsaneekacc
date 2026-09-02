import os
import hashlib
import hmac
from typing import Optional, Dict, Any
from database.repositories import UserRepository

class AuthService:
    def __init__(self, db_path: Optional[str] = None):
        self.user_repo = UserRepository(db_path)
        self.current_user: Optional[Dict[str, Any]] = None

    @staticmethod
    def hash_password(password: str, salt: Optional[bytes] = None) -> str:
        if salt is None:
            salt = os.urandom(16)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return salt.hex() + ":" + pwd_hash.hex()

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        try:
            salt_hex, hash_hex = stored_hash.split(':')
            salt = bytes.fromhex(salt_hex)
            expected_hash = bytes.fromhex(hash_hex)
            computed_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            return hmac.compare_digest(computed_hash, expected_hash)
        except Exception:
            return False

    def login(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        user = self.user_repo.get_by_username(username)
        if not user or not user.get('is_active'):
            return None
        if self.verify_password(password, user['password_hash']):
            self.current_user = user
            return user
        return None

    def create_initial_manager(self) -> None:
        """Create default manager if no users exist."""
        users = self.user_repo.list_users()
        if not users:
            admin_hash = self.hash_password("admin123")
            self.user_repo.create_user("admin", admin_hash, "مدیر سیستم", "manager")

    def check_permission(self, required_roles: list) -> bool:
        if not self.current_user:
            return False
        return self.current_user.get('role') in required_roles

    # Role check helpers
    def can_manage_users(self) -> bool:
        return self.check_permission(['manager'])

    def can_view_full_financial_reports(self) -> bool:
        return self.check_permission(['manager', 'accountant'])

    def can_manage_expenses(self) -> bool:
        return self.check_permission(['manager', 'accountant'])

    def can_backup_restore(self) -> bool:
        return self.check_permission(['manager', 'accountant'])

    def can_record_payment(self) -> bool:
        return self.check_permission(['manager', 'accountant', 'secretary'])

    def can_manage_students(self) -> bool:
        return self.check_permission(['manager', 'accountant', 'secretary'])
