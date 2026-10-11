#!/bin/sh
echo "Waiting for postgres..."
set -e  # Exit ngay nếu bất kỳ lệnh nào thất bại

# Thêm timeout để tránh loop vô hạn (ví dụ: 60 giây)
counter=0
while ! nc -z $DB_URL $DB_PORT; do
    sleep 0.1
    counter=$((counter + 1))
    if [ $counter -ge 600 ]; then  # 600 * 0.1s = 60s
        echo "Timeout: Không thể kết nối PostgreSQL sau 60 giây."
        exit 1
    fi
done
echo "PostgreSQL started"


# Chạy setup_db với debug

python manage.py recreate_db
# Đánh dấu migration đã được apply để tránh conflict
python manage.py db stamp head
python manage.py seed_db

gunicorn -b 0.0.0.0:$PORT manage:app