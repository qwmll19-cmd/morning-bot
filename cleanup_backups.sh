#!/bin/bash
# 백업 파일 정리 스크립트
# 안전하게 백업 파일들을 archive 폴더로 이동합니다.

echo "================================================"
echo "  🧹 백업 파일 정리 시작"
echo "================================================"
echo ""

# archive 폴더 생성
ARCHIVE_DIR="archive_backups_$(date +%Y%m%d)"
mkdir -p "$ARCHIVE_DIR"

echo "📁 Archive 폴더: $ARCHIVE_DIR"
echo ""

# 백업 파일 개수 확인
BACKUP_COUNT=$(find . -type f \( -name "*.backup" -o -name "*.20260102_*" \) | grep -v "$ARCHIVE_DIR" | wc -l)

echo "🔍 발견된 백업 파일: $BACKUP_COUNT 개"
echo ""

if [ "$BACKUP_COUNT" -eq 0 ]; then
    echo "✅ 정리할 백업 파일이 없습니다."
    exit 0
fi

echo "📋 백업 파일 목록:"
echo "------------------------------------------------"
find . -type f \( -name "*.backup" -o -name "*.20260102_*" \) | grep -v "$ARCHIVE_DIR" | head -20
echo ""

# 사용자 확인
read -p "이 파일들을 $ARCHIVE_DIR 로 이동하시겠습니까? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 취소되었습니다."
    exit 0
fi

echo ""
echo "🚀 파일 이동 중..."
echo ""

# 백업 파일 이동 (.backup)
MOVED_COUNT=0
while IFS= read -r file; do
    if [ -f "$file" ]; then
        # 디렉토리 구조 유지하며 이동
        DIR_PATH=$(dirname "$file")
        mkdir -p "$ARCHIVE_DIR/$DIR_PATH"
        mv "$file" "$ARCHIVE_DIR/$file"
        echo "  ✓ $file"
        MOVED_COUNT=$((MOVED_COUNT + 1))
    fi
done < <(find . -type f -name "*.backup" | grep -v "$ARCHIVE_DIR")

# 타임스탬프 백업 파일 이동 (.20260102_*)
while IFS= read -r file; do
    if [ -f "$file" ]; then
        DIR_PATH=$(dirname "$file")
        mkdir -p "$ARCHIVE_DIR/$DIR_PATH"
        mv "$file" "$ARCHIVE_DIR/$file"
        echo "  ✓ $file"
        MOVED_COUNT=$((MOVED_COUNT + 1))
    fi
done < <(find . -type f -name "*.20260102_*" | grep -v "$ARCHIVE_DIR")

echo ""
echo "================================================"
echo "  ✅ 정리 완료!"
echo "================================================"
echo ""
echo "📊 이동된 파일: $MOVED_COUNT 개"
echo "📁 저장 위치: $ARCHIVE_DIR"
echo ""
echo "💡 Tip: 나중에 필요 없으면 폴더 전체를 삭제하세요:"
echo "   rm -rf $ARCHIVE_DIR"
echo ""
