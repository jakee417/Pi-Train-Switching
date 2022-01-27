#!/bin/bash
usr_path="$HOME/.config/systemd/user"
service="train_switch.service"

echo "++++ Stopping $service"
systemctl --user stop $service
systemctl --user disable $service

echo "++++ Uninstalling $service in: $usr_path"
rm $usr_path/$service
systemctl --user daemon-reload
systemctl --user reset-failed

echo "Success"