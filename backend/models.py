# backend/models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# --- Bảng trung gian ---
dieu_kien_tien_quyet = db.Table('DieuKienTienQuyet',
    db.Column('MaHP', db.String(50), db.ForeignKey('HocPhan.MaHP'), primary_key=True),
    db.Column('MaHPTienQuyet', db.String(50), db.ForeignKey('HocPhan.MaHP'), primary_key=True)
)

# --- Các Bảng chính ---
class Khoa(db.Model):
    __tablename__ = 'Khoa'
    MaKhoa = db.Column(db.String(50), primary_key=True)
    TenKhoa = db.Column(db.String(255), nullable=False)
    nganh_hoc_rel = db.relationship('NganhHoc', backref='khoa', lazy='dynamic')

class NganhHoc(db.Model):
    __tablename__ = 'NganhHoc'
    MaNganh = db.Column(db.String(50), primary_key=True)
    TenNganh = db.Column(db.String(255), nullable=False)
    TongSoTinChi = db.Column(db.Integer, nullable=False, default=0)
    MaKhoa = db.Column(db.String(50), db.ForeignKey('Khoa.MaKhoa'), nullable=False)
    lop_hoc_rel = db.relationship('LopHoc', backref='nganh_hoc', lazy='dynamic')
    chuong_trinh_dao_tao_rel = db.relationship('ChuongTrinhDaoTao', backref='nganh_hoc', lazy='dynamic')

class LopHoc(db.Model):
    __tablename__ = 'LopHoc'
    MaLop = db.Column(db.String(50), primary_key=True)
    TenLop = db.Column(db.String(255), nullable=False)
    NamTuyenSinh = db.Column(db.Integer)
    MaNganh = db.Column(db.String(50), db.ForeignKey('NganhHoc.MaNganh'), nullable=False)
    sinh_vien_rel = db.relationship('SinhVien', backref='lop_hoc', lazy='dynamic')

class VaiTro(db.Model):
    __tablename__ = 'VaiTro'
    MaVaiTro = db.Column(db.Integer, primary_key=True, autoincrement=True)
    TenVaiTro = db.Column(db.String(50), unique=True, nullable=False)

class NguoiDung(db.Model):
    __tablename__ = 'NguoiDung'
    MaNguoiDung = db.Column(db.Integer, primary_key=True, autoincrement=True)
    TenDangNhap = db.Column(db.String(100), unique=True, nullable=False)
    MatKhauMaHoa = db.Column(db.String(255), nullable=False)
    Email = db.Column(db.String(255), unique=True, nullable=False)
    TrangThai = db.Column(db.String(50), nullable=False, default='Hoạt động')
    MaVaiTro = db.Column(db.Integer, db.ForeignKey('VaiTro.MaVaiTro'), nullable=False)
    vai_tro_rel = db.relationship('VaiTro', backref=db.backref('nguoi_dung_rel', lazy='dynamic'))
    sinh_vien_rel = db.relationship('SinhVien', back_populates='nguoi_dung_rel', uselist=False, cascade="all, delete-orphan")

class SinhVien(db.Model):
    __tablename__ = 'SinhVien'
    MaSV = db.Column(db.String(50), primary_key=True)
    HoTen = db.Column(db.String(100), nullable=False)
    NgaySinh = db.Column(db.Date, nullable=True)
    NoiSinh = db.Column(db.String(255), nullable=True)
    TrangThaiHocTap = db.Column(db.String(50), nullable=False, default='Đang học')
    MaLop = db.Column(db.String(50), db.ForeignKey('LopHoc.MaLop'), nullable=True)
    MaNguoiDung = db.Column(db.Integer, db.ForeignKey('NguoiDung.MaNguoiDung'), unique=True, nullable=False)
    nguoi_dung_rel = db.relationship('NguoiDung', back_populates='sinh_vien_rel')
    ket_qua_hoc_tap_rel = db.relationship('KetQuaHocTap', backref='sinh_vien', lazy='dynamic', cascade="all, delete-orphan")

class HocPhan(db.Model):
    __tablename__ = 'HocPhan'
    MaHP = db.Column(db.String(50), primary_key=True)
    TenHP = db.Column(db.String(255), nullable=False)
    SoTinChi = db.Column(db.Integer, nullable=False)
    KhoiKienThuc = db.Column(db.String(100), nullable=True)
    TinhDiemTichLuy = db.Column(db.Boolean, nullable=False, default=True)
    mon_tien_quyet = db.relationship( 'HocPhan', secondary=dieu_kien_tien_quyet,
        primaryjoin=(MaHP == dieu_kien_tien_quyet.c.MaHP),
        secondaryjoin=(MaHP == dieu_kien_tien_quyet.c.MaHPTienQuyet),
        backref=db.backref('la_tien_quyet_cho', lazy='dynamic')
    )

class ChuongTrinhDaoTao(db.Model):
    __tablename__ = 'ChuongTrinhDaoTao'
    MaCTDT = db.Column(db.Integer, primary_key=True, autoincrement=True)
    HocKyGoiY = db.Column(db.Integer, nullable=False)
    LaMonBatBuoc = db.Column(db.Boolean, default=True)
    MaNganh = db.Column(db.String(50), db.ForeignKey('NganhHoc.MaNganh'), nullable=False)
    MaHP = db.Column(db.String(50), db.ForeignKey('HocPhan.MaHP'), nullable=False)
    hoc_phan_rel = db.relationship('HocPhan')

class KetQuaHocTap(db.Model):
    __tablename__ = 'KetQuaHocTap'
    MaKQ = db.Column(db.Integer, primary_key=True, autoincrement=True)
    HocKy = db.Column(db.String(50), nullable=False)
    DiemHe10 = db.Column(db.Float, nullable=False)
    DiemHe4 = db.Column(db.Float)
    DiemChu = db.Column(db.String(5))
    LaDiemCuoiCung = db.Column(db.Boolean, default=True, nullable=False)
    MaSV = db.Column(db.String(50), db.ForeignKey('SinhVien.MaSV'), nullable=False)
    MaHP = db.Column(db.String(50), db.ForeignKey('HocPhan.MaHP'), nullable=False)
    hoc_phan_rel = db.relationship('HocPhan', backref='ket_qua_hoc_tap_rel')

class SystemConfig(db.Model):
    __tablename__ = 'SystemConfig'
    ConfigKey = db.Column(db.String(50), primary_key=True)
    ConfigValue = db.Column(db.String(255), nullable=False)
    Description = db.Column(db.String(255), nullable=True)