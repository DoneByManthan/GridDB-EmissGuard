#!/usr/bin/env bash
# setup.sh — One-shot environment setup for EmissGuard on Ubuntu 24.04
set -e

echo "======================================================"
echo "  EmissGuard — Environment Setup"
echo "======================================================"

echo ""
echo "[1/5] Checking Python ..."
python3 --version

echo ""
echo "[2/5] Creating virtual environment ..."
if [ -d "venv" ]; then
    echo "  venv/ already exists — skipping."
else
    python3 -m venv --system-site-packages venv
    echo "  ✓ venv created with --system-site-packages"
fi

echo ""
echo "[3/5] Upgrading pip ..."
source venv/bin/activate
pip install --upgrade pip --quiet
echo "  ✓ pip upgraded"

echo ""
echo "[4/5] Installing Python dependencies ..."
pip install -r requirements.txt
echo "  ✓ All packages installed"

echo ""
echo "[5/5] Verifying griddb_python ..."
python3 -c "import griddb_python as griddb; print('  ✓ griddb_python found:', griddb.__file__)" || {
    echo "  ✗ griddb_python not found."
    echo "    Install GridDB system-wide first:"
    echo "    https://docs.griddb.net/latest/gettingstarted/using-apt/"
    exit 1
}

echo ""
echo "======================================================"
echo "  EmissGuard setup complete."
echo ""
echo "  Activate:    source venv/bin/activate"
echo "  Insert data: cd src && python insert_data.py"
echo "  Start API:   python app.py"
echo "  Dashboard:   http://localhost:5050"
echo "======================================================"
