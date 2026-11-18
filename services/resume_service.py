"""Extracts plain text from uploaded resume files (PDF / DOCX)."""
import os


def extract_text(file_path):
    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        return _extract_pdf(file_path)
    if ext == "docx":
        return _extract_docx(file_path)
    raise ValueError(f"Unsupported resume file type: {ext}")


def _extract_pdf(file_path):
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)
    return "\n".join(text_parts).strip()


def _extract_docx(file_path):
    import docx
    document = docx.Document(file_path)
    paragraphs = [p.text for p in document.paragraphs if p.text]
    return "\n".join(paragraphs).strip()


def save_upload(file_storage, upload_folder, stored_filename):
    os.makedirs(upload_folder, exist_ok=True)
    destination = os.path.join(upload_folder, stored_filename)
    file_storage.save(destination)
    return destination


_MAGIC_BYTES = {
    "pdf": (b"%PDF",),
    "docx": (b"PK\x03\x04",),  # docx is a zip archive
}


def sniff_matches_extension(file_storage, extension):
    """Reads the file's leading bytes to confirm it's actually a PDF/DOCX,
    not just a file renamed to look like one. Resets the stream afterward
    so the caller can still .save() it."""
    signatures = _MAGIC_BYTES.get(extension)
    if not signatures:
        return False
    header = file_storage.stream.read(8)
    file_storage.stream.seek(0)
    return any(header.startswith(sig) for sig in signatures)


def can_view_resume(user, resume):
    """Who may view/download a given resume: its owner, an admin, or a
    company whose internship that EXACT resume was submitted against.

    Deliberately keyed on Application.resume_id == resume.id, not just
    "this company received some application from this student" - a company
    must never see a resume the student used for a different, unrelated
    application just because the two happen to share a student. A student
    who has since uploaded a newer resume for other applications keeps
    their older resume private from companies that never received it."""
    if user.role == "admin":
        return True
    if user.role == "student":
        return resume.student_profile.user_id == user.id
    if user.role == "company" and user.company:
        from database.models import Application, Internship
        return Application.query.join(Internship).filter(
            Application.resume_id == resume.id,
            Internship.company_id == user.company.id,
        ).first() is not None
    return False
