from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
import jwt
from flask import abort, g, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from common import create_base, data, db, integer, pagination, text


def authenticated(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        from flask import current_app
        token = request.headers.get("Authorization", "")
        if not token.startswith("Bearer "):
            abort(401,"Sign in to continue.")
        try:
            claims = jwt.decode(token[7:],current_app.config["SECRET_KEY"],algorithms=["HS256"],issuer="task-platform",options={"require":["exp","iat","sub","iss"]})
            g.user_id = int(claims["sub"])
        except (jwt.InvalidTokenError,ValueError,TypeError):
            abort(401,"Session expired or invalid. Sign in again.")
        if not db().execute("SELECT id FROM users WHERE id=?",(g.user_id,)).fetchone():
            abort(401,"Account no longer exists.")
        return fn(*args,**kwargs)
    return wrapped


def owned_project(project_id):
    if not db().execute("SELECT id FROM projects WHERE id=? AND user_id=?",(project_id,g.user_id)).fetchone():
        abort(404,"Project not found.")


def create_app(config=None):
    app = create_base(config)
    with app.app_context():
        db().executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),name TEXT NOT NULL,UNIQUE(user_id,name));
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,title TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('todo','doing','done')),created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS tasks_project ON tasks(project_id,id);
        """)

    @app.get("/")
    def index():
        dist = Path(app.root_path)/"frontend"/"dist"
        if not (dist/"index.html").exists():
            return "Build the frontend first: cd frontend && npm ci && npm run build",503
        return send_from_directory(dist,"index.html")

    @app.get("/assets/<path:filename>")
    def assets(filename):
        return send_from_directory(Path(app.root_path)/"frontend"/"dist"/"assets",filename)

    @app.post("/api/register")
    def register():
        p = data()
        username = text(p.get("username"),"Username",80)
        password = text(p.get("password"),"Password",200)
        if len(password) < 10:
            abort(400,"Use a password of at least 10 characters.")
        db().execute("INSERT INTO users(username,password) VALUES(?,?)",(username,generate_password_hash(password)))
        db().commit()
        return {"message":"Account created. Sign in to continue."},201

    @app.post("/api/login")
    def login():
        p = data()
        user = db().execute("SELECT * FROM users WHERE username=?",(text(p.get("username"),"Username",80),)).fetchone()
        password = text(p.get("password"),"Password",200)
        if not user or not check_password_hash(user["password"],password):
            abort(401,"Invalid username or password.")
        now = datetime.now(timezone.utc)
        token = jwt.encode({"sub":str(user["id"]),"iat":now,"exp":now+timedelta(hours=1),"iss":"task-platform"},app.config["SECRET_KEY"],algorithm="HS256")
        return {"token":token,"username":user["username"],"expires_in":3600}

    @app.get("/api/projects")
    @authenticated
    def projects():
        return {"items":[dict(r) for r in db().execute("SELECT id,name FROM projects WHERE user_id=? ORDER BY id DESC",(g.user_id,))]}

    @app.route("/api/projects",methods=["POST"])
    @app.route("/api/projects/<int:project_id>",methods=["PUT","DELETE"])
    @authenticated
    def save_project(project_id=None):
        if project_id:
            owned_project(project_id)
        if request.method == "DELETE":
            db().execute("DELETE FROM projects WHERE id=?",(project_id,))
        else:
            name = text(data().get("name"),"Project name")
            if project_id:
                db().execute("UPDATE projects SET name=? WHERE id=?",(name,project_id))
            else:
                project_id = db().execute("INSERT INTO projects(user_id,name) VALUES(?,?)",(g.user_id,name)).lastrowid
        db().commit()
        return {"id":project_id,"message":"Project saved."},201 if request.method == "POST" else 200

    @app.get("/api/tasks")
    @authenticated
    def tasks():
        try:
            project_id = int(request.args.get("project_id",""))
        except ValueError:
            abort(400,"A project_id is required.")
        owned_project(project_id)
        page,limit = pagination()
        rows = db().execute("SELECT * FROM tasks WHERE project_id=? ORDER BY id DESC LIMIT ? OFFSET ?",(project_id,limit,(page-1)*limit)).fetchall()
        total = db().execute("SELECT count(*) FROM tasks WHERE project_id=?",(project_id,)).fetchone()[0]
        return {"items":[dict(r) for r in rows],"total":total,"page":page,"limit":limit}

    @app.route("/api/tasks",methods=["POST"])
    @app.route("/api/tasks/<int:task_id>",methods=["PUT","DELETE"])
    @authenticated
    def save_task(task_id=None):
        if task_id:
            task = db().execute("SELECT t.* FROM tasks t JOIN projects p ON p.id=t.project_id WHERE t.id=? AND p.user_id=?",(task_id,g.user_id)).fetchone()
            if not task:
                abort(404,"Task not found.")
        if request.method == "DELETE":
            db().execute("DELETE FROM tasks WHERE id=?",(task_id,))
        else:
            p = data()
            title = text(p.get("title"),"Task title",200)
            status = p.get("status","todo")
            if not isinstance(status, str) or status not in {"todo","doing","done"}:
                abort(400,"Choose todo, doing or done.")
            if task_id:
                db().execute("UPDATE tasks SET title=?,status=? WHERE id=?",(title,status,task_id))
            else:
                project_id = integer(p.get("project_id"),"Project",1,2147483647)
                owned_project(project_id)
                task_id = db().execute("INSERT INTO tasks(project_id,title,status,created_at) VALUES(?,?,?,?)",(project_id,title,status,datetime.now(timezone.utc).isoformat())).lastrowid
        db().commit()
        return {"id":task_id,"message":"Task saved."},201 if request.method == "POST" else 200

    return app
