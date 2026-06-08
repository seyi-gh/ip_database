#!/bin/bash
cd "$(dirname "$0")"

echo "> Installing ip-database service..."
sudo cp ip-database.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ip-database
sudo systemctl start ip-database

echo "> Status:"
sudo systemctl status ip-database --no-pager
