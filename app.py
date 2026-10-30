"""Flask application coordinating upload, retrieval, and Gemini answers."""
import logging
import secrets
import time
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
from config import Config
from document_processor import extract_pages, chunk_pages
from embeddings import GeminiService
from retrieval import retrieve

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.config.from_object(Config)
if not app.config["SECRET_KEY"]:
    app.config["SECRET_KEY"] = secrets.token_hex(32)
    logging.warning("FLASK_SECRET_KEY is unset; using an ephemeral key. Sessions reset on restart.")

_documents = {}  # Demo-only in-memory storage; keyed by a random per-browser session ID.
MAX_QUESTIONS = 30


def _service():
    return GeminiService(app.config["GEMINI_API_KEY"], app.config["EMBEDDING_MODEL"],
                         app.config["GEMINI_MODEL"])


def _doc():
    key = session.get("document_id")
    document = _documents.get(key) if key else None
    if document:
        document["last_access"] = time.time()
    return document


@app.before_request
def protect_post_requests():
    timeout = app.config["PERMANENT_SESSION_LIFETIME"]
    now = time.time()
    expired = [key for key, value in _documents.items()
               if now - value.get("last_access", value.get("created_at", now)) > timeout]
    for key in expired:
        _documents.pop(key, None)
    if request.method == "POST":
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "")
        if not expected or not secrets.compare_digest(expected, supplied):
            flash("This form expired. Please try again.", "warning")
            return redirect(url_for("index"))


def _safe_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "api key" in message or "unauthenticated" in message or "permission" in message:
        return "Gemini rejected the API key or access. Check your key and model access in the .env file."
    if "quota" in message or "resource_exhausted" in message or "429" in message:
        return "Gemini quota or rate limit reached. Wait and try again, or check API usage and billing."
    if ("not found" in message or "no longer available" in message
            or ("model" in message and ("unsupported" in message or "unavailable" in message))):
        return "The configured Gemini model is unavailable. Check GEMINI_MODEL in .env."
    if "timeout" in message or "network" in message or "connection" in message:
        return "Could not reach Gemini. Check your internet connection and try again."
    return "Gemini could not process this request. Check the server log for details and try again."


@app.errorhandler(RequestEntityTooLarge)
def too_large(_error):
    flash("The upload exceeds the 10 MB limit.", "danger")
    return redirect(url_for("index")), 303


@app.get("/")
def index():
    session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return render_template("index.html", document=_doc())


@app.get("/favicon.ico")
def favicon():
    return "", 204


@app.post("/upload")
def upload():
    uploaded = request.files.get("document")
    if not uploaded or not uploaded.filename:
        flash("Choose a PDF file to upload.", "danger")
        return redirect(url_for("index"))
    safe_name = secure_filename(uploaded.filename)
    if not safe_name or not safe_name.lower().endswith(".pdf"):
        flash("Only files with a .pdf extension are accepted.", "danger")
        return redirect(url_for("index"))
    data = uploaded.read(app.config["MAX_CONTENT_LENGTH"] + 1)
    if not data:
        flash("The uploaded file is empty.", "danger")
        return redirect(url_for("index"))
    if len(data) > app.config["MAX_CONTENT_LENGTH"]:
        flash("The upload exceeds the 10 MB limit.", "danger")
        return redirect(url_for("index"))
    try:
        pages = extract_pages(data, app.config["MAX_PAGES"])
        chunks = [chunk.as_dict() for chunk in chunk_pages(
            pages, app.config["CHUNK_SIZE"], app.config["CHUNK_OVERLAP"])]
        service = _service()
        # Embed one at a time to keep each API request small and easy to understand.
        for chunk in chunks:
            chunk["embedding"] = service.embed(chunk["text"], "RETRIEVAL_DOCUMENT",
                                               title=safe_name)
        old_id = session.get("document_id")
        if old_id:
            _documents.pop(old_id, None)
        document_id = secrets.token_urlsafe(24)
        _documents[document_id] = {"filename": safe_name, "pages": len(pages),
                                   "chunks": chunks, "history": [],
                                   "created_at": time.time(), "last_access": time.time()}
        session["document_id"] = document_id
        session.permanent = True
        flash(f"Processed {safe_name}: {len(pages)} pages, {len(chunks)} text chunks.", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        logging.exception("Document processing failed")
        flash(_safe_error(exc), "danger")
    return redirect(url_for("index"))


@app.post("/ask")
def ask():
    document = _doc()
    if not document:
        flash("Your document session has expired. Upload the PDF again.", "warning")
        session.pop("document_id", None)
        return redirect(url_for("index"))
    question = request.form.get("question", "").strip()
    if not question:
        flash("Enter a question first.", "danger")
        return redirect(url_for("index"))
    if len(question) > 2000:
        flash("Keep your question under 2,000 characters.", "danger")
        return redirect(url_for("index"))
    if len(document["history"]) >= MAX_QUESTIONS:
        flash("This session reached 30 questions. Reset the document to continue.", "warning")
        return redirect(url_for("index"))
    try:
        service = _service()
        query_vector = service.embed(question, "RETRIEVAL_QUERY")
        passages = retrieve(document["chunks"], query_vector, app.config["TOP_K"])
        if not passages or max(p["similarity"] for p in passages) <= 0:
            flash("No relevant text could be matched to that question. Try rephrasing it.", "warning")
            return redirect(url_for("index"))
        answer = service.answer(question, passages)
        sources = sorted({p["page_start"] for p in passages})
        document["history"].append({"question": question, "answer": answer, "sources": sources})
    except Exception as exc:
        logging.exception("Question answering failed")
        flash(_safe_error(exc), "danger")
    return redirect(url_for("index"))


@app.post("/reset")
def reset():
    old_id = session.pop("document_id", None)
    if old_id:
        _documents.pop(old_id, None)
    flash("Document and conversation cleared.", "info")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=False)
