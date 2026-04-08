@echo off
cd C:\Users\socce\Desktop\pitwall-ai\pitwall-backend
call .venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
