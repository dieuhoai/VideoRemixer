#!/bin/bash
cd "$(dirname "$0")"
echo ""
echo "╔══════════════════════════════════════╗"
echo "║     Video Bulk Remixer               ║"
echo "║     Đang khởi động...                ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[LỖI] Chưa cài Python 3. Tải tại: https://www.python.org/downloads/"
    read -p "Bấm Enter để đóng..."
    exit 1
fi

# Setup venv if needed
if [ ! -d ".venv" ]; then
    echo "[1/3] Tạo môi trường ảo..."
    python3 -m venv .venv
    echo "[2/3] Cài thư viện..."
    .venv/bin/pip install -e ".[dev]" --quiet
    echo "[3/3] Xong!"
else
    echo "Môi trường đã sẵn sàng."
fi

echo ""
echo "Đang mở giao diện..."
echo "Đóng cửa sổ này hoặc bấm Ctrl+C để thoát."
echo ""
.venv/bin/python -m web.server
