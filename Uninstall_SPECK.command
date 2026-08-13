#!/bin/bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="speck"
FOUND_CONDA=""

echo "============================================"
echo "  SPECK Uninstaller"
echo "============================================"
echo

echo "[1/4] Looking for the Conda/Miniforge installation..."
for candidate in "$HOME/miniforge3" "$HOME/mambaforge" "$HOME/anaconda3" "$HOME/miniconda3" "/opt/miniforge3" "/opt/homebrew/Caskroom/miniforge/base"; do
    if [ -f "$candidate/bin/conda" ]; then
        FOUND_CONDA="$candidate"
        break
    fi
done

if [ -z "$FOUND_CONDA" ]; then
    echo "      No Conda/Miniforge installation found - nothing to remove there."
else
    echo "      Found installation at $FOUND_CONDA"
    echo
    echo "[2/4] Removing the speck environment..."
    "$FOUND_CONDA/bin/conda" env remove -n "$ENV_NAME" -y
fi

echo
echo "[3/4] Removing the launch shortcut..."
PARENT_DIR="$(cd "$DIR/.." && pwd)"
if [ -f "$PARENT_DIR/SPECK.command" ]; then
    rm -f "$PARENT_DIR/SPECK.command"
    echo "      Shortcut removed."
else
    echo "      No shortcut found next to the SPECK folder - skipping."
fi

echo
echo "[4/4] Miniforge itself..."
if [ -z "$FOUND_CONDA" ]; then
    echo "      Nothing to do - no Conda/Miniforge installation was found."
elif [ -f "$FOUND_CONDA/.installed_by_speck" ]; then
    echo "      This Miniforge installation was installed by the SPECK installer"
    echo "      and is not used by any other software you set up yourself."
    read -p "      Remove Miniforge entirely as well? [y/N] " REPLY
    case "$REPLY" in
        [Yy]*)
            rm -rf "$FOUND_CONDA"
            echo "      Miniforge removed."
            ;;
        *)
            echo "      Leaving Miniforge installed."
            ;;
    esac
else
    echo "      This Conda/Miniforge installation already existed on this machine"
    echo "      before SPECK was installed, so it is being left alone - removing it"
    echo "      could break other software that depends on it."
fi

echo
echo "============================================"
echo "  Uninstall complete."
echo "  The SPECK folder itself (including any saved"
echo "  sessions or exports) has not been touched."
echo "  Delete it manually once you've backed up"
echo "  anything you want to keep."
echo "============================================"
echo
read -p "Press Return to close this window..."
