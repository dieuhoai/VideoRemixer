#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo ""
echo "╔══════════════════════════════════════╗"
echo "║     Video Bulk Remixer               ║"
echo "║     Đang khởi động...                ║"
echo "╚══════════════════════════════════════╝"
echo ""

fail() {
    echo ""
    echo "[LỖI] $1"
    read -r -p "Bấm Enter để đóng..."
    exit 1
}

# Tìm Python 3.10 trở lên (macOS hay có sẵn Python 3.9 quá cũ)
PY=""
for cand in python3.13 python3.12 python3.11 python3.10 \
            /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
            /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
            /usr/local/bin/python3 /opt/homebrew/bin/python3 python3; do
    if command -v "$cand" >/dev/null 2>&1 &&
       "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        PY="$cand"
        break
    fi
done
[ -n "$PY" ] || fail "Chưa có Python 3.10 trở lên. Tải tại https://www.python.org/downloads/ rồi chạy lại."

CHECK='import fastapi, uvicorn, numpy, cv2, PIL'

# Tạo môi trường và cài thư viện nếu chưa có (hoặc đang hỏng)
if ! .venv/bin/python -c "$CHECK" >/dev/null 2>&1; then
    echo "[1/3] Tạo môi trường ảo..."
    rm -rf .venv
    "$PY" -m venv .venv || fail "Không tạo được môi trường ảo."

    echo "[2/3] Cài thư viện (có thể mất vài phút)..."
    .venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1
    if ! .venv/bin/python -m pip install .; then
        rm -rf .venv
        fail "Cài thư viện thất bại. Chụp lại các dòng lỗi phía trên và gửi cho người hỗ trợ."
    fi
    if ! .venv/bin/python -c "$CHECK" >/dev/null 2>&1; then
        rm -rf .venv
        fail "Thư viện cài xong nhưng không dùng được. Chụp lại các dòng lỗi và gửi cho người hỗ trợ."
    fi
    echo "[3/3] Xong!"
else
    echo "Môi trường đã sẵn sàng."
fi

echo ""
echo "Đang mở giao diện..."
echo "Đóng cửa sổ này hoặc bấm Ctrl+C để thoát."
echo ""
.venv/bin/python -m web.server
