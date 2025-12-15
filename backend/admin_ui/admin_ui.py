from flask import Blueprint, render_template

bp = Blueprint(
    "admin_ui",
    __name__,
    url_prefix="/admin",
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

@bp.get("/")
def admin_index():
    return render_template("index.html")
