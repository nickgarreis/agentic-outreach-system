# src/routers/__init__.py
# Router package initialization
# Exports all routers for easy import in main.py
# RELEVANT FILES: auth.py, client_members.py, ../main.py

from .auth import router as auth_router
from .client_members import router as client_members_router

__all__ = ["auth_router", "client_members_router"]
