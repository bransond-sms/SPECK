#!/bin/bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="speck"
MINIFORGE_DIR=""
FOUND_CONDA=""

echo "============================================"
echo "  SPECK Installer"
echo "============================================"
echo

echo "[1/5] Checking for an existing Conda/Miniforge installation..."
for candidate in "$HOME/miniforge3" "$HOME/mambaforge" "$HOME/anaconda3" "$HOME/miniconda3" "/opt/miniforge3" "/opt/homebrew/Caskroom/miniforge/base"; do
    if [ -f "$candidate/bin/conda" ]; then
        FOUND_CONDA="$candidate"
        break
    fi
done

if [ -n "$FOUND_CONDA" ]; then
    echo "      Found existing installation at $FOUND_CONDA"
    MINIFORGE_DIR="$FOUND_CONDA"
else
    echo "      None found. We'll install Miniforge now - this only happens once."
    MINIFORGE_DIR="$HOME/miniforge3"
    echo
    echo "[2/5] Downloading Miniforge - this may take a few minutes..."
    ARCH="$(uname -m)"
    INSTALLER="${TMPDIR:-/tmp}/miniforge_installer.sh"
    curl -fsSL -o "$INSTALLER" "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-${ARCH}.sh"

    if [ ! -f "$INSTALLER" ]; then
        echo
        echo "      ERROR: Download failed. Check your internet connection and try again."
        echo "      If this keeps happening, copy this message and send it to Drake."
        read -p "Press Return to close this window..."
        exit 1
    fi

    echo "      Installing Miniforge silently to $MINIFORGE_DIR ..."
    bash "$INSTALLER" -b -p "$MINIFORGE_DIR"
    rm -f "$INSTALLER"

    if [ ! -f "$MINIFORGE_DIR/bin/conda" ]; then
        echo
        echo "      ERROR: Miniforge install did not complete as expected."
        echo "      Copy this message and send it to Drake."
        read -p "Press Return to close this window..."
        exit 1
    fi
    echo "      Miniforge installed successfully."
    echo "This file marks that the SPECK installer installed Miniforge on this machine, so Uninstall_SPECK.command knows it is safe to remove. Do not delete this file manually." > "$MINIFORGE_DIR/.installed_by_speck"
fi

echo
echo "[3/5] Setting up the SPECK environment..."
if "$MINIFORGE_DIR/bin/conda" env list | grep -q "^${ENV_NAME} "; then
    echo "      Existing SPECK environment found - updating it to match the latest requirements..."
    "$MINIFORGE_DIR/bin/conda" env update -n "$ENV_NAME" -f "$DIR/environment.yml" --prune
else
    echo "      Creating the SPECK environment for the first time - this takes a few minutes..."
    "$MINIFORGE_DIR/bin/conda" env create -n "$ENV_NAME" -f "$DIR/environment.yml"
fi

if [ $? -ne 0 ]; then
    echo
    echo "      ERROR: Environment setup failed. Copy the messages above and send them to Drake."
    read -p "Press Return to close this window..."
    exit 1
fi

echo
echo "[4/5] Creating a shortcut next to the SPECK folder..."
PARENT_DIR="$(cd "$DIR/.." && pwd)"
cat > "$PARENT_DIR/SPECK.command" <<WRAPPER
#!/bin/bash
exec "$DIR/SPECK.sh"
WRAPPER
chmod +x "$PARENT_DIR/SPECK.command"

echo
echo "[5/5] All done!"
echo "============================================"
echo "  SPECK is installed. Use the \"SPECK\" shortcut"
echo "  next to the SPECK folder to launch it from now on."
echo "  You will not need to run this installer again"
echo "  unless Drake sends you an update."
echo "============================================"
echo
read -p "Press Return to close this window..."
