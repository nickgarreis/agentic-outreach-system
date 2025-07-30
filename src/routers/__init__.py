# src/routers/__init__.py
# Router package initialization
# Exports all routers for easy import in main.py
# RELEVANT FILES: auth.py, ../main.py

from .auth import router as auth_router

__all__ = ["auth_router"]
