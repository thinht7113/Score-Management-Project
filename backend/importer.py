# backend/importer.py
import pandas as pd
from datetime import datetime
from passlib.hash import bcrypt
from models import db, HocPhan, SinhVien, NguoiDung, LopHoc, VaiTro, NganhHoc, KetQuaHocTap, ChuongTrinhDaoTao


def parse_date(date_string, student_id):
    """
    Hàm "bất tử" để xử lý nhiều định dạng ngày tháng.
    Trả về một đối tượng date hoặc None.
    """
    if not date_string or pd.isna(date_string):
        return None

    print(
        f"DEBUG: Đang xử lý ngày sinh cho SV '{student_id}'. Giá trị gốc: '{date_string}' (Kiểu: {type(date_string)})")

    date_string = str(date_string)

    formats_to_try = [
        '%d/%m/%Y',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%d-%m-%Y',
    ]
    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_string.split(" ")[0], fmt).date()
        except (ValueError, TypeError):
            continue

    print(f"CẢNH BÁO: Không thể nhận diện định dạng ngày tháng cho SV '{student_id}'. Giá trị: '{date_string}'")
    return None


class FullDataImporter:
    """
    Xử lý file Excel chứa thông tin đầy đủ của một lớp học:
    danh sách sinh viên, danh sách môn học (từ header), và điểm số.
    Thực hiện 'upsert' cho các thực thể liên quan.
    """

    def __init__(self, file_path, ma_nganh):
        self.file_path = file_path; self.ma_nganh = ma_nganh; self.errors = []
        self.stats = {'students_found': 0, 'students_created': 0, 'classes_created': 0, 'courses_created': 0, 'grades_created': 0, 'grades_skipped': 0}

        with db.session.no_autoflush:
            self.role_sv = VaiTro.query.filter_by(TenVaiTro='Sinh viên').first()
            self.nganh_hoc = db.session.get(NganhHoc, self.ma_nganh)
            self.existing_sv = {sv.MaSV: sv for sv in SinhVien.query.all()}
            self.existing_lops = {lop.MaLop: lop for lop in LopHoc.query.all()}
            self.existing_hps_by_name = {hp.TenHP: hp for hp in HocPhan.query.all()}
            self.existing_grades = {f"{kq.MaSV}-{kq.MaHP}" for kq in KetQuaHocTap.query.all()}

    def run(self):
        """Hàm chính điều phối toàn bộ quá trình import."""
        try:
            df, course_details = self._prepare_dataframe()
            if df.empty:
                self.errors.append(
                    "Không tìm thấy dòng dữ liệu sinh viên hợp lệ trong file (kiểm tra lại định dạng Mã SV).")
                return True, self.errors, self.stats

            self._upsert_courses(course_details)
            self._upsert_students_and_classes(df)
            self._upsert_grades(df, course_details)

            print("Đang commit tất cả các thay đổi vào CSDL...")
            db.session.commit()
            print("Commit thành công!")
            return True, self.errors, self.stats

        except Exception as e:
            db.session.rollback()
            import traceback;
            traceback.print_exc()
            self.errors.append(f"Lỗi hệ thống nghiêm trọng, mọi thay đổi đã được thu hồi: {str(e)}")
            return False, self.errors, None

    def _prepare_dataframe(self):
        """Đọc và xử lý file Excel, trích xuất thông tin môn học từ header."""
        df_raw = pd.read_excel(self.file_path, header=[0, 1], dtype=str).fillna('')

        course_details = {}
        student_info_cols = ['Số TT', 'Mã sinh viên', 'Họ và tên', 'Ngày sinh', 'Nơi sinh', 'Tên lớp', 'TBC HT10',
                             'TBC HT4', 'Xếp loại thang 4', 'Xếp loại thang 10', 'Số HP nợ', 'Số tín chỉ nợ',
                             'Người tổng hợp', 'Ngày tổng hợp']

        # Làm phẳng header và trích xuất thông tin môn học
        processed_columns = []
        for col_header1, col_header2 in df_raw.columns:
            clean_name = col_header1.strip()
            processed_columns.append(clean_name)
            if clean_name not in student_info_cols:
                try:
                    # Logic xác định môn không tính GPA ngay tại đây
                    is_gpa_course = "giáo dục thể chất" not in clean_name.lower()
                    course_details[clean_name] = {"SoTinChi": int(col_header2), "TinhDiemTichLuy": is_gpa_course}
                except (ValueError, TypeError):
                    self.errors.append(f"Cảnh báo: Không thể đọc số tín chỉ cho cột '{clean_name}'.")

        df_raw.columns = processed_columns
        # Lọc bỏ các dòng không phải dữ liệu sinh viên
        df_clean = df_raw[df_raw['Mã sinh viên'].astype(str).str.match(r'^\d{2}A\d+')].copy()

        return df_clean, course_details

    def _upsert_courses(self, course_details):
        """Tìm hoặc tạo mới các Học phần trong CSDL."""
        print("Đang xử lý và tạo mới các Học phần...")
        for ten_hp, details in course_details.items():
            if ten_hp not in self.existing_hps_by_name:
                ma_hp_temp = ten_hp.replace(" ", "").replace("-", "").upper()[:20]
                new_hp = HocPhan(
                    MaHP=ma_hp_temp, TenHP=ten_hp,
                    SoTinChi=details["SoTinChi"],
                    TinhDiemTichLuy=details.get("TinhDiemTichLuy", True)
                )
                db.session.add(new_hp)
                self.existing_hps_by_name[ten_hp] = new_hp  # Cập nhật cache
                self.stats['courses_created'] += 1
        db.session.flush()

    def _upsert_students_and_classes(self, df_students):
        """Tìm hoặc tạo mới Sinh viên, Lớp học, và tài khoản Người dùng."""
        unique_students = df_students.drop_duplicates(subset=['Mã sinh viên'])
        print(f"Đang xử lý {len(unique_students)} sinh viên duy nhất...")
        self.stats['students_found'] = len(unique_students)

        for _, row in unique_students.iterrows():
            ma_sv = row['Mã sinh viên'].strip();
            ten_lop = row['Tên lớp'].strip()
            if ma_sv in self.existing_sv: continue

            if ten_lop not in self.existing_lops:
                lop = LopHoc(MaLop=ten_lop, TenLop=ten_lop, NamTuyenSinh=2022, nganh_hoc=self.nganh_hoc)
                db.session.add(lop);
                self.existing_lops[ten_lop] = lop
                self.stats['classes_created'] += 1

            hashed_password = bcrypt.hash(ma_sv)
            new_user = NguoiDung(TenDangNhap=ma_sv, MatKhauMaHoa=hashed_password, Email=f"{ma_sv}@hvu.edu.vn",
                                 vai_tro_rel=self.role_sv)

            ngay_sinh_dt = parse_date(row['Ngày sinh'], ma_sv)

            new_student = SinhVien(
                MaSV=ma_sv, HoTen=row['Họ và tên'], NgaySinh=ngay_sinh_dt,
                NoiSinh=row['Nơi sinh'], MaLop=ten_lop, nguoi_dung_rel=new_user
            )

            db.session.add(new_user);
            db.session.add(new_student)
            self.existing_sv[ma_sv] = new_student
            self.stats['students_created'] += 1

        db.session.flush()

    def _upsert_grades(self, df_wide, course_details):
        """Xử lý và ghi điểm vào CSDL."""
        print("Đang xử lý và tạo mới các bản ghi điểm số...")
        grade_cols = list(course_details.keys())
        df_long = pd.melt(df_wide, id_vars=['Mã sinh viên'], value_vars=grade_cols, var_name='TenHP',
                          value_name='DiemHe10')

        df_long['DiemHe10'] = df_long['DiemHe10'].astype(str).str.replace(',', '.', regex=False)
        df_long['DiemHe10'] = pd.to_numeric(df_long['DiemHe10'], errors='coerce')
        df_long.dropna(subset=['DiemHe10'], inplace=True)

        for _, row in df_long.iterrows():
            ma_sv, ten_hp, diem_he_10 = row['Mã sinh viên'], row['TenHP'], row['DiemHe10']

            hoc_phan = self.existing_hps_by_name.get(ten_hp.strip())
            if not hoc_phan: self.stats['grades_skipped'] += 1; continue

            if f"{ma_sv}-{hoc_phan.MaHP}" in self.existing_grades: self.stats['grades_skipped'] += 1; continue

            diem_he_4, diem_chu = 0.0, 'F'
            if diem_he_10 >= 8.5:
                diem_he_4, diem_chu = 4.0, 'A'
            elif diem_he_10 >= 7.0:
                diem_he_4, diem_chu = 3.0, 'B'
            elif diem_he_10 >= 5.5:
                diem_he_4, diem_chu = 2.0, 'C'
            elif diem_he_10 >= 4.0:
                diem_he_4, diem_chu = 1.0, 'D'

            # TODO: Logic xác định học kỳ từ chương trình đào tạo
            new_grade = KetQuaHocTap(MaSV=ma_sv, MaHP=hoc_phan.MaHP, HocKy="Imported", DiemHe10=diem_he_10,
                                     DiemHe4=diem_he_4, DiemChu=diem_chu, LaDiemCuoiCung=True)
            db.session.add(new_grade)
            self.stats['grades_created'] += 1


class CurriculumImporter:
    """Importer chuyên dụng chỉ để đọc và xử lý file Chương trình Đào tạo."""

    def __init__(self, file_path, ma_nganh):
        self.file_path = file_path
        self.ma_nganh = ma_nganh
        self.errors = []
        self.stats = {'courses_created': 0, 'curriculum_entries_created': 0}

    def run(self):
        try:
            # ===> ĐỌC FILE VỚI CHỈ 1 DÒNG HEADER <===
            df = pd.read_excel(self.file_path, header=0, dtype=str).fillna('')

            # Tải trước dữ liệu cần thiết để kiểm tra trùng lặp
            existing_hps = {hp.MaHP for hp in HocPhan.query.with_entities(HocPhan.MaHP).all()}
            existing_ctdt = {f"{c.MaNganh}-{c.MaHP}" for c in ChuongTrinhDaoTao.query.all()}

            for index, row in df.iterrows():
                # Dùng .get() để tránh lỗi nếu thiếu cột
                ma_hp = str(row.get('Mã học phần', '')).strip()
                ten_hp = str(row.get('Tên học phần', '')).strip()
                if not ma_hp or not ten_hp: continue

                # 1. TẠO HỌC PHẦN NẾU CHƯA CÓ
                if ma_hp not in existing_hps:
                    is_gpa_course = "giáo dục thể chất" not in ten_hp.lower()
                    new_hp = HocPhan(
                        MaHP=ma_hp,
                        TenHP=ten_hp,
                        SoTinChi=int(row['Số tín chỉ']),
                        KhoiKienThuc=str(row.get('Khối kiến thức', '')).strip(),
                        TinhDiemTichLuy=is_gpa_course
                    )
                    db.session.add(new_hp)
                    existing_hps.add(ma_hp)  # Thêm vào cache
                    self.stats['courses_created'] += 1

                # 2. TẠO LIÊN KẾT CHƯƠNG TRÌNH ĐÀO TẠO NẾU CHƯA CÓ
                ctdt_key = f"{self.ma_nganh}-{ma_hp}"
                if ctdt_key not in existing_ctdt:
                    is_mandatory = str(row.get('Bắt buộc', '')).strip().lower() == 'x'
                    new_ctdt = ChuongTrinhDaoTao(
                        MaNganh=self.ma_nganh,
                        MaHP=ma_hp,
                        HocKyGoiY=int(row['Kỳ thứ']),
                        LaMonBatBuoc=is_mandatory
                    )
                    db.session.add(new_ctdt)
                    existing_ctdt.add(ctdt_key)  # Thêm vào cache
                    self.stats['curriculum_entries_created'] += 1

            db.session.commit()
            return True, self.errors, self.stats
        except Exception as e:
            db.session.rollback()
            import traceback;
            traceback.print_exc()
            self.errors.append(f"Lỗi hệ thống: {str(e)}")
            return False, self.errors, None