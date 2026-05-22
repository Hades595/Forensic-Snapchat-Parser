import os
import jinja2
from datetime import datetime


def generate_report(case_name: str, snaps: list, output_path: str, examiner: str = "") -> str:
    template_dir = os.path.join(os.path.dirname(__file__), "..", "html")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
    template = env.get_template("report_template.html")

    processed_snaps = []
    for snap in snaps:
        s = snap.copy()
        if s.get("file_path"):
            s["file_path"] = os.path.relpath(s["file_path"], output_path).replace(os.sep, "/")
        processed_snaps.append(s)

    html = template.render(
        case_name=case_name,
        examiner=examiner,
        platform="Android",
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        snap_count=len(processed_snaps),
        snaps=processed_snaps,
    )

    report_path = os.path.join(output_path, "forensic_report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    return report_path
