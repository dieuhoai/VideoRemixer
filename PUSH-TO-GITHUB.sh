#!/bin/bash
# ═══════════════════════════════════════════
#  Push Video Bulk Remixer lên GitHub
#  Chỉ cần chạy 1 lần, hỏi username + tạo repo tự động
# ═══════════════════════════════════════════
set -e
cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  Push VideoRemixer lên GitHub        ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Hỏi username
read -p "GitHub username của bạn: " GH_USER
if [ -z "$GH_USER" ]; then echo "Cần nhập username!"; exit 1; fi

REPO_NAME="VideoRemixer"
REPO_URL="https://github.com/$GH_USER/$REPO_NAME.git"

echo ""
echo "Sẽ tạo repo: https://github.com/$GH_USER/$REPO_NAME"
echo ""

# Tạo repo qua GitHub CLI nếu có, hoặc hướng dẫn tạo tay
if command -v gh &> /dev/null; then
    echo "Phát hiện GitHub CLI → tạo repo tự động..."
    gh repo create "$REPO_NAME" --public --description "Tạo hàng trăm biến thể video quảng cáo — thay đoạn, audio, text hàng loạt" || true
else
    echo "Chưa có GitHub CLI. Tạo repo tay:"
    echo "  1. Mở https://github.com/new"
    echo "  2. Tên: $REPO_NAME · Public · KHÔNG tích README/gitignore"
    echo "  3. Bấm Create repository"
    echo ""
    read -p "Đã tạo xong? Bấm Enter để tiếp..."
fi

# Push
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
git branch -M main
echo ""
echo "Đang push..."
git push -u origin main

echo ""
echo "✅ Xong! Repo tại: https://github.com/$GH_USER/$REPO_NAME"
echo ""
