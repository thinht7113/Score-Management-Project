# Student Performance Visualization & AI Advisor
**(Phần mềm Desktop Trực quan hóa Kết quả Học tập & Cố vấn AI)**

> Ứng dụng Desktop giúp sinh viên theo dõi và trực quan hóa dữ liệu học tập cá nhân, tích hợp AI (Google Gemini) để phân tích xu hướng và đưa ra lời khuyên cải thiện điểm số.

---

## 🛠 Công nghệ sử dụng

| Thành phần | Công nghệ | Chi tiết |
| :--- | :--- | :--- |
| **Core Language** | Python 3.10+ | |
| **Backend API** | Flask | RESTful API, xử lý nghiệp vụ, xác thực JWT. |
| **Database** | SQLite + SQLAlchemy | ORM, thiết kế CSDL quan hệ chuẩn hóa. |
| **Desktop Client** | CustomTkinter | GUI hiện đại (Dark/Light mode), Matplotlib (Biểu đồ). |
| **Admin Web** | HTML/CSS/Bootstrap | Giao diện quản trị viên trên trình duyệt. |
| **AI Integration** | Google Gemini API | Phân tích dữ liệu học tập, Chatbot cố vấn. |

---

## 🏗 Kiến trúc Hệ thống

Hệ thống hoạt động theo mô hình **Client-Server**:

1.  **Backend (Server):** Chạy API trung tâm, quản lý Database, xử lý Logic cảnh báo học vụ và phân quyền.
2.  **Student App (Client):** Ứng dụng Desktop kết nối tới Backend qua API để lấy dữ liệu và vẽ biểu đồ trực quan cho sinh viên.

---

## 🚀 Chức năng chính

### 1. Student App (Dành cho Sinh viên)
* **Trực quan hóa dữ liệu (Visualization):** Biểu đồ xu hướng GPA qua các kỳ, phân tích môn điểm cao/thấp.
* **Mô phỏng GPA (Simulator):** Tính toán kịch bản điểm số (VD: *"Nếu kỳ này môn A được 8.0 thì CPA sẽ tăng bao nhiêu?"*).
* **Cố vấn AI (AI Advisor):** Chatbot tích hợp Gemini, đưa ra lời khuyên dựa trên bảng điểm thực tế của sinh viên.
* **Tra cứu:** Xem chi tiết bảng điểm, tín chỉ và tiến độ học tập.

### 2. Admin Web (Dành cho Quản lý)
* **Dashboard:** Thống kê tổng quan sinh viên, học phần.
* **Hệ thống cảnh báo (Warning System):** Tự động quét sinh viên có nguy cơ (GPA thấp, nợ tín chỉ vượt mức) theo luật cấu hình động.
* **Quản lý dữ liệu:** Import danh sách Sinh viên, Điểm, Chương trình đào tạo từ file Excel.

---

## ⚙️ Cài đặt & Hướng dẫn sử dụng

### Yêu cầu
* Python 3.10 trở lên.
* Hệ điều hành: Windows, macOS hoặc Linux.

### Bước 1: Cài đặt môi trường
```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường (Windows)
.venv\Scripts\activate

# Cài đặt thư viện
pip install -r requirements.txt
