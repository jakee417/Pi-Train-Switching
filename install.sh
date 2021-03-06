#!/bin/bash
usr_path="$HOME/.config/systemd/user"
service="train_switch.service"

echo "++++ Installing $service in: $usr_path"
mkdir -p $usr_path
cp $service  $usr_path/$service
systemctl --user daemon-reload

echo "++++ Enabling $service"
systemctl --user enable $service

echo "++++ Starting $service"
systemctl --user start $service

echo "Success"