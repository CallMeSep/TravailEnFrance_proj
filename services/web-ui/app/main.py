import os
from urllib.parse import urlencode

import requests
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
API_BASE_URL = os.getenv("JOB_API_BASE_URL", "http://localhost:8000")
INGESTION_BASE_URL = os.getenv("JOB_INGESTION_BASE_URL", "http://job-ingestion-service:8080")
UI_HOST = os.getenv("UI_HOST", "0.0.0.0")
UI_PORT = int(os.getenv("UI_PORT", "3000"))
PAGE_SIZE = 9
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-this-secret")


def current_user():
    return session.get("user")


def favorite_job_ids_for_user(user):
    if not user:
        return set()
    user_id = user.get("id")
    if not user_id:
        return set()
    try:
        response = requests.get(f"{API_BASE_URL}/users/{user_id}/favorites", timeout=10)
        response.raise_for_status()
        return set(response.json().get("job_ids", []))
    except Exception:
        return set()


def _build_search_terms(title: str, type_contrat: str, commune: str) -> str:
    parts = [x.strip() for x in (title, type_contrat, commune) if x and x.strip()]
    return ", ".join(parts)


def _trigger_ingestion_for_search(search_terms: str) -> None:
    if not search_terms:
        return
    try:
        requests.post(
            f"{INGESTION_BASE_URL}/run-now",
            json={"search_terms": search_terms},
            timeout=120,
        )
    except Exception:
        # Search can still continue using existing indexed DB data.
        pass


@app.route("/")
def index():
    page = request.args.get("page", default=1, type=int)
    if page < 1:
        page = 1

    title = request.args.get("title", default="", type=str).strip()
    type_contrat = request.args.get("type_contrat", default="", type=str).strip()
    commune = request.args.get("commune", default="", type=str).strip()

    offset = (page - 1) * PAGE_SIZE
    api_params = {"limit": PAGE_SIZE, "offset": offset}
    if title:
        api_params["title"] = title
    if type_contrat:
        api_params["type_contrat"] = type_contrat
    if commune:
        api_params["commune"] = commune

    api_unreachable = False
    try:
        response = requests.get(
            f"{API_BASE_URL}/jobs",
            params=api_params,
            timeout=10,
        )
        response.raise_for_status()
        jobs = response.json()
    except Exception:
        jobs = []
        api_unreachable = True

    # If user is searching and DB has no hits, trigger ingestion with a single
    # comma-separated query (e.g. "python, CDI, Paris"), then retry once.
    search_terms = _build_search_terms(title, type_contrat, commune)
    if page == 1 and not jobs and search_terms and not api_unreachable:
        _trigger_ingestion_for_search(search_terms)
        try:
            response = requests.get(
                f"{API_BASE_URL}/jobs",
                params=api_params,
                timeout=15,
            )
            response.raise_for_status()
            jobs = response.json()
        except Exception:
            jobs = []
            api_unreachable = True

    has_prev = page > 1
    has_next = len(jobs) == PAGE_SIZE
    user = current_user()
    favorite_ids = favorite_job_ids_for_user(user)
    search_params = {
        "title": title,
        "type_contrat": type_contrat,
        "commune": commune,
    }

    return render_template(
        "index.html",
        jobs=jobs,
        api_unreachable=api_unreachable,
        page=page,
        has_prev=has_prev,
        has_next=has_next,
        user=user,
        favorite_ids=favorite_ids,
        search_params=search_params,
        query_string=urlencode(search_params),
    )


@app.route("/jobs/<job_id>")
def job_detail(job_id: str):
    response = requests.get(f"{API_BASE_URL}/jobs/{job_id}", timeout=10)
    if response.status_code == 404:
        abort(404)
    response.raise_for_status()
    job = response.json()
    user = current_user()
    favorite_ids = favorite_job_ids_for_user(user)
    return render_template("job_detail.html", job=job, user=user, favorite_ids=favorite_ids)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        dob_raw = request.form.get("dob", "").strip()
        primary_skill = request.form.get("skill", "").strip()
        skills_raw = request.form.get("skills", "").strip()

        if not username or not password or not dob_raw:
            flash("Username, password and date of birth are required.")
            return render_template("register.html")

        skill_names = [s.strip() for s in skills_raw.split(",") if s.strip()]
        payload = {
            "username": username,
            "password": password,
            "dob": dob_raw,
            "skill": primary_skill or None,
            "skills": skill_names,
        }
        try:
            response = requests.post(f"{API_BASE_URL}/auth/register", json=payload, timeout=10)
            if response.status_code >= 400:
                detail = response.json().get("detail", "Registration failed")
                flash(str(detail))
                return render_template("register.html")
        except Exception:
            flash("Cannot reach backend auth service.")
            return render_template("register.html")

        flash("Account created. You can now log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=10,
            )
            if response.status_code >= 400:
                flash("Invalid username or password.")
                return render_template("login.html")
            data = response.json()
            session["user"] = {"id": data["user_id"], "username": data["username"]}
        except Exception:
            flash("Cannot reach backend auth service.")
            return render_template("login.html")
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/favorites")
def favorites():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    user_id = user.get("id")
    favorite_ids = favorite_job_ids_for_user(user)
    jobs = []
    for job_id in favorite_ids:
        try:
            response = requests.get(f"{API_BASE_URL}/jobs/{job_id}", timeout=10)
            if response.status_code == 200:
                jobs.append(response.json())
        except Exception:
            continue

    return render_template("favorites.html", jobs=jobs, user=user, favorite_ids=favorite_ids, user_id=user_id)


@app.post("/favorite/<job_id>")
def toggle_favorite(job_id: str):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    user_id = user.get("id")
    try:
        requests.post(f"{API_BASE_URL}/users/{user_id}/favorites/{job_id}", timeout=10)
    except Exception:
        flash("Could not update favorites right now.")

    next_url = request.args.get("next") or url_for("index")
    return redirect(next_url)


if __name__ == "__main__":
    app.run(host=UI_HOST, port=UI_PORT)
