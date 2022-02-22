#!/bin/bash

function install {
    echo -e "Installing Linguard..."
    # Include hidden files (.*)
    shopt -s dotglob
    # Move all files to exported path
    mv "$DATA_PATH"/* "$EXPORTED_PATH"
}

function run {
    echo -e "Running Linguard..."
    # Link conf files to install path
    rm -rf "$DATA_PATH"
    ln -s "$EXPORTED_PATH" "$DATA_PATH"
    chown -R linguard:linguard "$DATA_PATH"
    chown -R linguard:linguard "$EXPORTED_PATH"
    # Start server
    ls -l "$EXPORTED_PATH"
    sudo -u linguard dotnet "$INSTALL_PATH/Linguard.Web.Dll"
}

flag_file="$EXPORTED_PATH/.times_ran"
count=1
if [ ! -f "$flag_file" ]; then
    install
else
    count=$(cat "$flag_file")
    let "count++"
fi
echo "$count" > "$flag_file"
run