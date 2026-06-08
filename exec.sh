#!/bin/bash
venv/bin/python3 -B -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload