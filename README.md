# Hệ Thống Quản Lý Điểm Sinh Viên & Trợ Lý Học Tập (Score Management System)

Dự án phần mềm quản lý điểm sinh viên tích hợp ứng dụng dành cho sinh viên với các tính năng thông minh như Mô phỏng GPA và Trợ lý ảo AI.

## 🏗️ Kiến trúc Hệ thống

Hệ thống bao gồm 2 thành phần chính hoạt động song song:

1.  **Backend & Admin Web**:
    *   **Ngôn ngữ**: Python (Flask Framework).
    *   **Cơ sở dữ liệu**: SQLite (SQLAlchemy ORM).
    *   **Giao diện Admin**: Web-based (HTML/CSS/JavaScript + Bootstrap).
    *   **Chức năng**: Quản lý dữ liệu sinh viên, học phần, điểm số, cấu hình hệ thống, và quét cảnh báo học vụ.

2.  **Student App (Desktop)**:
    *   **Ngôn ngữ**: Python.
    *   **Giao diện**: Desktop GUI (CustomTkinter).
    *   **Chức năng**: Xem bảng điểm, lộ trình học, biểu đồ phân tích, mô phỏng cải thiện điểm (GPA Simulator), và Cố vấn học tập AI (Gemini integration).

---

## 🚀 Tính năng nổi bật

### 1. Dành cho Quản trị viên (Admin Web)
*   **Bảng điều khiển (Dashboard)**: Thống kê tổng quan sinh viên, học phần.
*   **Nhập dữ liệu (Import)**: Hỗ trợ nhập danh sách sinh viên, điểm, chương trình học từ Excel.
*   **Quản lý Cảnh báo (Warning System)**:
    *   Tự động quét và phát hiện sinh viên có nguy cơ (GPA thấp, nợ nhiều tín chỉ).
    *   Cấu hình các luật cảnh báo linh hoạt (VD: GPA < 2.0).
*   **Quản lý người dùng**: Phân quyền Admin/User.

### 2. Dành cho Sinh viên (Student App)
*   **Tổng quan cá nhân**: Biểu đồ xu hướng GPA theo kỳ, Top môn điểm cao/thấp.
*   **Tra cứu bảng điểm & Chương trình học**: Xem chi tiết điểm số, tiến độ hoàn thành chương trình.
*   **Mô phỏng GPA (Simulator)**:
    *   Cho phép giả định điểm các môn sắp học hoặc học lại.
    *   Tính toán tự động CPA dự kiến.
    *   Gợi ý điểm số cần đạt để đạt mục tiêu (VD: Muốn CPA 3.2 thì cần TB các môn còn lại bao nhiêu?).
*   **Cố vấn AI (Advisor)**:
    *   Chatbot tích hợp Google Gemini AI.
    *   Tư vấn lộ trình học, phương pháp học tập dựa trên dữ liệu điểm thực tế của sinh viên.

---

## 🛠️ Hướng dẫn Cài đặt & Chạy

### Yêu cầu hệ thống
*   Python 3.10 trở lên.
*   Hệ điều hành: Windows/macOS/Linux.

### Bước 1: Cài đặt thư viện
Khuyến khích sử dụng môi trường ảo (`venv`).
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt
```
*(Nếu chưa có file `requirements.txt`, các thư viện chính: `flask`, `sqlalchemy`, `customtkinter`, `pandas`, `matplotlib`, `google-generativeai`, `openpyxl`)*

### Bước 2: Cấu hình môi trường
Tạo file `.env` trong thư mục `backend` (hoặc root tùy cấu hình) với nội dung:
```env

# Cấu hình Google Gemini AI (cho tính năng Cố vấn)
GEMINI_API_KEY=YOUR_API_KEY_HERE
GEMINI_MODEL=gemini-2.0-flash-exp
```

### Bước 3: Khởi tạo dữ liệu (Lần đầu)
Chạy script seed để tạo dữ liệu mẫu và tài khoản admin mặc định:
```bash
python -m backend.seed
```
*Tài khoản mặc định: `admin` / `admin123`*

### Bước 4: Chạy Hệ thống

**1. Khởi chạy Server (Backend & Admin UI)**
Mở terminal và chạy lệnh:
```bash
python -m backend.app
```
*   Server sẽ chạy tại: `http://127.0.0.1:5000`
*   Truy cập Admin Web tại địa chỉ trên.

**2. Khởi chạy Ứng dụng Sinh viên**
Mở thêm một terminal mới (vẫn trong môi trường ảo):
```bash
python -m student.app
```
*   Đăng nhập bằng mã sinh viên (nếu dữ liệu đã được import) hoặc tài khoản người dùng được cấp.

---

## 📂 Cấu trúc thư mục

```
Score Management Project/
├── backend/                # Source code Backend
│   ├── admin_ui/           # Giao diện Web Admin (Templates/Static)
│   ├── app.py              # File khởi chạy Flask App
│   ├── admin_crud.py       # API endpoints cho Admin
│   ├── warning_scan.py     # Logic quét cảnh báo học vụ
│   ├── models.py           # Định nghĩa Database Models
│   └── seed.py             # Dữ liệu mẫu
│
├── student/                # Source code Student App
│   ├── views/              # Các màn hình (Overview, Transcript, Simulator...)
│   ├── widgets/            # Các component UI (Charts, Cards...)
│   └── app.py              # File khởi chạy Student App
│
├── logs/                   # Thư mục chứa log hệ thống
└── README.md               # Tài liệu hướng dẫn
```

## 📝 Ghi chú phát triển
*   **Customize UI (Student)**: Sửa đổi các file trong `student/theme/`.
*   **Thay đổi Logic Cảnh báo**: Cập nhật file `backend/warning_scan.py`.
*   **API tích hợp**: Swagger/OpenAPI chưa tích hợp sẵn, tham khảo `backend/admin_crud.py` để xem danh sách API.
