import os
from sqlalchemy import create_engine
from app.auth import create_user, authenticate_user, get_user_with_role

engine = create_engine("postgresql://admin:admin@localhost:5432/signdb")

try:
    user = create_user("testuser", "test@voya.com", "password123", is_admin=False)
    print("Created user:", user)
except Exception as e:
    print("User creation error (might exist):", e)

auth_user = authenticate_user("testuser", "password123")
print("Auth user:", auth_user)

if auth_user:
    full_user = get_user_with_role(auth_user['id'])
    print("Full user details:", full_user)
