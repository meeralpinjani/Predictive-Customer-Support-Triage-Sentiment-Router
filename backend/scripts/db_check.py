"""Prints the database state for start-demo.ps1: ok | empty | down: <reason>."""
from sqlalchemy import inspect

try:
    from app.db import engine
    print("ok" if "tickets" in inspect(engine).get_table_names() else "empty")
except Exception as exc:  # unreachable server, wrong password, missing DATABASE_URL...
    print(f"down: {type(exc).__name__}")
