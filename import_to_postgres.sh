#!/bin/bash
cd "$(dirname "$0")"
venv/bin/python3 -B _pg_import/pg_import.py
