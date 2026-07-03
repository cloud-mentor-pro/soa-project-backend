# Hướng dẫn Cài đặt và Chạy Backend

Tài liệu này hướng dẫn cách cài đặt môi trường và chạy ứng dụng backend bằng Docker và Docker Compose.

## Yêu cầu

Trước khi bắt đầu, hãy chắc chắn rằng bạn đã cài đặt các phần mềm sau:

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Cài đặt

1.  **Clone repository**

    ```bash
    git clone https://github.com/cloud-mentor-pro/soa-project-backend.git
    cd soa-project-backend
    ```

## Chạy ứng dụng

1.  **Build và khởi chạy các container**
    - Vào thư mục dự án và cấp quyền cần thiết cho `entrypoint.sh`
    ```bash
    cd soa-project-backend
    # sudo chmod+x backend/entrypoint.sh
    ```
    Sử dụng lệnh sau để build các image và khởi chạy các container cho môi trường phát triển:

    ```bash
    docker-compose -f docker-compose-dev.yml up -d --build
    ```

    - `-d`: Chạy các container ở chế độ detached (chạy nền).
    - `--build`: Build lại các image trước khi khởi chạy.

2.  **Kiểm tra trạng thái các container**

    Để chắc chắn rằng các container đã được khởi chạy thành công, bạn có thể dùng lệnh:

    ```bash
    docker-compose -f docker-compose-dev.yml ps
    ```

    Bạn sẽ thấy trạng thái `Up` cho các service `backend` và `db`.

3.  **Tạo database và migrations** (chỉ chạy khi có update schema bình thường không cần chạy )
    - Khi có thay đổi schema db thì cần chạy các câu lênh bên dưới :
    Sau khi các container đã chạy, bạn cần thực thi các lệnh sau để tạo database và áp dụng migrations:

    ```bash
    docker-compose -f docker-compose-dev.yml exec backend python manage.py db migrate
    docker-compose -f docker-compose-dev.yml exec backend python manage.py db upgrade
    ```

## Truy cập ứng dụng

-   **API Backend**: Ứng dụng Flask sẽ chạy và có thể truy cập tại `http://localhost:5001`.
-   **Database**: Cơ sở dữ liệu PostgreSQL có thể được truy cập từ máy host tại `localhost:5435` với thông tin đăng nhập sau:
    -   **User**: `postgres`
    -   **Password**: `postgres`

## TODO


## API Healthcheck
```
http://localhost:5001/users/ping
```

## Dừng ứng dụng

```bash
# Dừng và xóa tất cả containers, networks
docker-compose -f docker-compose-dev.yml down

# Xóa containers + volumes
docker-compose -f docker-compose-dev.yml down -v

# Xóa containers + volumes + images
docker-compose -f docker-compose-dev.yml down -v --rmi all

# Xóa tất cả (containers, networks, volumes, images)
docker-compose -f docker-compose-dev.yml down -v --rmi all --remove-orphans