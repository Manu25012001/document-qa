"""Flask application coordinating upload, retrieval, and Gemini answers."""
import logging
import secrets
import time
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
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

# Cached Gemini service instance — avoids rebuilding the SDK client on every request.
_gemini_service: GeminiService | None = None


def _service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService(app.config["GEMINI_API_KEY"],
                                        app.config["EMBEDDING_MODEL"],
                                        app.config["GEMINI_MODEL"])
    return _gemini_service


def _doc():
    key = session.get("document_id")
    document = _documents.get(key) if key else None
    if document:
        document["last_access"] = time.time()
    return document


def _wants_json():
    """Return True when the client prefers a JSON response (AJAX)."""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@app.before_request
def protect_post_requests():
    timeout = app.config["PERMANENT_SESSION_LIFETIME"].total_seconds()
    now = time.time()
    expired = [key for key, value in _documents.items()
               if now - value.get("last_access", value.get("created_at", now)) > timeout]
    for key in expired:
        _documents.pop(key, None)
    if request.method == "POST":
        expected = session.get("csrf_token", "")
        supplied = (request.form.get("csrf_token", "")
                    or request.headers.get("X-CSRF-Token", ""))
        if not expected or not secrets.compare_digest(expected, supplied):
            if _wants_json():
                return jsonify({"success": False,
                                "error": "Session expired. Please refresh the page."}), 403
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
    if _wants_json():
        return jsonify({"success": False, "error": "The upload exceeds the 10 MB limit."}), 413
    flash("The upload exceeds the 10 MB limit.", "danger")
    return redirect(url_for("index")), 303


@app.get("/")
def index():
    session.setdefault("csrf_token", secrets.token_urlsafe(32))
    doc = _doc()
    initial_state = {
        "csrfToken": session["csrf_token"],
        "document": None,
        "maxQuestions": MAX_QUESTIONS,
        "geminiModel": app.config.get("GEMINI_MODEL", "gemini-3-flash-preview"),
        "embeddingModel": app.config.get("EMBEDDING_MODEL", "gemini-embedding-001"),
    }
    if doc:
        initial_state["document"] = {
            "filename": doc["filename"],
            "pages": doc["pages"],
            "chunks_count": len(doc["chunks"]),
            "history": doc["history"],
        }
    return render_template("index.html", document=doc, initial_state=initial_state)


@app.get("/favicon.ico")
def favicon():
    return "", 204


@app.post("/upload")
def upload():
    uploaded = request.files.get("document")
    if not uploaded or not uploaded.filename:
        msg = "Choose a PDF file to upload."
        if _wants_json():
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for("index"))
    safe_name = secure_filename(uploaded.filename)
    if not safe_name or not safe_name.lower().endswith(".pdf"):
        msg = "Only files with a .pdf extension are accepted."
        if _wants_json():
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for("index"))
    data = uploaded.read(app.config["MAX_CONTENT_LENGTH"] + 1)
    if not data:
        msg = "The uploaded file is empty."
        if _wants_json():
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for("index"))
    if len(data) > app.config["MAX_CONTENT_LENGTH"]:
        msg = "The upload exceeds the 10 MB limit."
        if _wants_json():
            return jsonify({"success": False, "error": msg}), 413
        flash(msg, "danger")
        return redirect(url_for("index"))
    try:
        pages = extract_pages(data, app.config["MAX_PAGES"])
        chunks = [chunk.as_dict() for chunk in chunk_pages(
            pages, app.config["CHUNK_SIZE"], app.config["CHUNK_OVERLAP"])]
        service = _service()
        # Batch-embed all chunks to minimize API round-trips.
        texts = [chunk["text"] for chunk in chunks]
        embeddings = service.embed_batch(texts, "RETRIEVAL_DOCUMENT", title=safe_name)
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding
        old_id = session.get("document_id")
        if old_id:
            _documents.pop(old_id, None)
        document_id = secrets.token_urlsafe(24)
        _documents[document_id] = {"filename": safe_name, "pages": len(pages),
                                   "chunks": chunks, "history": [],
                                   "created_at": time.time(), "last_access": time.time()}
        session["document_id"] = document_id
        session.permanent = True
        result = {"filename": safe_name, "pages": len(pages),
                  "chunks_count": len(chunks), "history": []}
        info = f"Processed {safe_name}: {len(pages)} pages, {len(chunks)} text chunks."
        if _wants_json():
            return jsonify({"success": True, "document": result, "message": info})
        flash(info, "success")
    except ValueError as exc:
        if _wants_json():
            return jsonify({"success": False, "error": str(exc)}), 400
        flash(str(exc), "danger")
    except Exception as exc:
        logging.exception("Document processing failed")
        error_msg = _safe_error(exc)
        if _wants_json():
            return jsonify({"success": False, "error": error_msg}), 500
        flash(error_msg, "danger")
    return redirect(url_for("index"))


@app.post("/ask")
def ask():
    document = _doc()
    if not document:
        msg = "Your document session has expired. Upload the PDF again."
        session.pop("document_id", None)
        if _wants_json():
            return jsonify({"success": False, "error": msg, "expired": True}), 410
        flash(msg, "warning")
        return redirect(url_for("index"))
    question = request.form.get("question", "").strip()
    if not question:
        msg = "Enter a question first."
        if _wants_json():
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for("index"))
    if len(question) > 2000:
        msg = "Keep your question under 2,000 characters."
        if _wants_json():
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for("index"))
    if len(document["history"]) >= MAX_QUESTIONS:
        msg = "This session reached 30 questions. Reset the document to continue."
        if _wants_json():
            return jsonify({"success": False, "error": msg}), 429
        flash(msg, "warning")
        return redirect(url_for("index"))
    try:
        service = _service()
        query_vector = service.embed(question, "RETRIEVAL_QUERY")
        passages = retrieve(document["chunks"], query_vector, app.config["TOP_K"])
        if not passages or max(p["similarity"] for p in passages) <= 0:
            msg = "No relevant text could be matched to that question. Try rephrasing it."
            if _wants_json():
                return jsonify({"success": False, "error": msg}), 404
            flash(msg, "warning")
            return redirect(url_for("index"))
        answer = service.answer(question, passages)
        sources = sorted({p["page_start"] for p in passages})
        clean_passages = [
            {"page_start": p.get("page_start", 1),
             "page_end": p.get("page_end", p.get("page_start", 1)),
             "text": p.get("text", ""),
             "similarity": round(float(p.get("similarity", 0.0)), 4)}
            for p in passages
        ]
        history_entry = {
            "question": question,
            "answer": answer,
            "sources": sources,
            "passages": clean_passages,
            "timestamp": time.time(),
        }
        document["history"].append(history_entry)
        if _wants_json():
            return jsonify({
                "success": True,
                "question": question,
                "answer": answer,
                "sources": sources,
                "passages": clean_passages,
            })
    except Exception as exc:
        logging.exception("Question answering failed")
        error_msg = _safe_error(exc)
        if _wants_json():
            return jsonify({"success": False, "error": error_msg}), 500
        flash(error_msg, "danger")
    return redirect(url_for("index"))


@app.post("/reset")
def reset():
    old_id = session.pop("document_id", None)
    if old_id:
        _documents.pop(old_id, None)
    if _wants_json():
        return jsonify({"success": True, "message": "Document and conversation cleared."})
    flash("Document and conversation cleared.", "info")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=False)
