# backend/models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


db = SQLAlchemy()



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
    MaNganh = db.Column(db.String(50), db.ForeignKey('NganhHoc.MaNganh'), nullable=True)
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

class ChuongTrinhDaoTao(db.Model):
    __tablename__ = 'ChuongTrinhDaoTao'
    MaCTDT = db.Column(db.Integer, primary_key=True, autoincrement=True)
    HocKy = db.Column(db.Integer, nullable=False)
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
    TinhDiemTichLuy = db.Column(db.Boolean, default=True, nullable=False)

    MaSV = db.Column(db.String(50), db.ForeignKey('SinhVien.MaSV'), nullable=False)
    MaHP = db.Column(db.String(50), db.ForeignKey('HocPhan.MaHP'), nullable=False)
    hoc_phan_rel = db.relationship('HocPhan', backref='ket_qua_hoc_tap_rel')

class SystemConfig(db.Model):
    __tablename__ = 'SystemConfig'
    ConfigKey = db.Column(db.String(50), primary_key=True)
    ConfigValue = db.Column(db.String(255), nullable=False)
    Description = db.Column(db.String(255), nullable=True)

class GradeAuditLog(db.Model):
    __tablename__ = "GradeAuditLog"
    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    MaSV = db.Column(db.String(50), nullable=False)
    MaHP = db.Column(db.String(50), nullable=False)
    HocKy = db.Column(db.String(50), nullable=False)
    Action = db.Column(db.String(30), nullable=False)  # create|update|approve|reject|import
    OldHe10 = db.Column(db.Float, nullable=True)
    NewHe10 = db.Column(db.Float, nullable=True)
    ActorId = db.Column(db.Integer, db.ForeignKey('NguoiDung.MaNguoiDung'), nullable=False)
    Source = db.Column(db.String(20), nullable=True)   # draft|manual|import
    MaPC = db.Column(db.Integer, nullable=True)
    At = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)



class WarningRule(db.Model):
    __tablename__ = "WarningRule"
    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Code = db.Column(db.String(50), unique=True, nullable=False)
    Name = db.Column(db.String(100), nullable=False)
    Threshold = db.Column(db.Float, nullable=False)
    Active = db.Column(db.Boolean, default=True, nullable=False)
    Desc = db.Column(db.String(255), nullable=True)

class WarningCase(db.Model):
    __tablename__ = "WarningCase"
    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    RuleId = db.Column(db.Integer, db.ForeignKey('WarningRule.Id'), nullable=False)
    MaSV = db.Column(db.String(50), db.ForeignKey('SinhVien.MaSV'), nullable=False)
    Value = db.Column(db.Float, nullable=False)
    Level = db.Column(db.String(20), nullable=True)
    Status = db.Column(db.String(20), default="open", nullable=False)
    CreatedAt = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ClosedAt = db.Column(db.DateTime, nullable=True)

class ImportLog(db.Model):
    __tablename__ = "ImportLog"
    RunId = db.Column(db.Integer, primary_key=True, autoincrement=True)
    When = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    Actor = db.Column(db.String(64), nullable=True)
    Endpoint = db.Column(db.String(128), nullable=False)
    Params = db.Column(db.Text, nullable=True)
    Filename = db.Column(db.String(256), nullable=True)
    Summary = db.Column(db.Text, nullable=True)
    AffectedTable = db.Column(db.String(64), nullable=True)
    InsertedIds = db.Column(db.Text, nullable=True)

class AuditLog(db.Model):
    __tablename__ = "AuditLog"
    Id = db.Column(db.Integer, primary_key=True)
    At = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    Actor = db.Column(db.String(64), index=True)
    Action = db.Column(db.String(64), index=True)
    Resource = db.Column(db.String(64), index=True)
    ResourceId = db.Column(db.String(64), index=True)
    Before = db.Column(db.JSON, nullable=True)
    After = db.Column(db.JSON, nullable=True)
    ClientIP = db.Column(db.String(48), nullable=True)
    UA = db.Column(db.String(256), nullable=True)

