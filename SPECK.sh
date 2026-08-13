#!/bin/bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="speck"
MINIFORGE_DIR=""

for candidate in "$HOME/miniforge3" "$HOME/mambaforge" "$HOME/anaconda3" "$HOME/miniconda3" "/opt/miniforge3" "/opt/homebrew/Caskroom/miniforge/base"; do
    if [ -f "$candidate/bin/conda" ]; then
        MINIFORGE_DIR="$candidate"
        break
    fi
done

if [ -z "$MINIFORGE_DIR" ]; then
    echo "Could not find a Conda/Miniforge installation."
    echo "Please run Install_SPECK.command first."
    read -p "Press Return to close this window..."
    exit 1
fi

source "$MINIFORGE_DIR/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

cd "$DIR"
python main.py

if [ $? -ne 0 ]; then
    echo
    echo "SPECK exited with an error. Copy the messages above and send them to Drake."
    read -p "Press Return to close this window..."
fi
