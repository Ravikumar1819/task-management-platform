import jwt
import pytest
from datetime import datetime,timedelta,timezone
from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING":True,"DATABASE":str(tmp_path/"test.db"),"SECRET_KEY":"test-secret-123456789012345678901234"})


def login(client,name="alice"):
    payload={"username":name,"password":"test-password-123"}
    assert client.post("/api/register",json=payload).status_code == 201
    r=client.post("/api/login",json=payload)
    assert r.status_code == 200
    return {"Authorization":"Bearer "+r.json["token"]}


def test_crud_pagination_and_ownership(app):
    c=app.test_client()
    assert c.get("/api/projects").status_code == 401
    h=login(c)
    p=c.post("/api/projects",json={"name":"Portfolio"},headers=h).json["id"]
    for i in range(3):
        assert c.post("/api/tasks",json={"project_id":p,"title":f"Task {i}"},headers=h).status_code == 201
    r=c.get(f"/api/tasks?project_id={p}&limit=2",headers=h).json
    assert len(r["items"]) == 2 and r["total"] == 3
    tid=r["items"][0]["id"]
    assert c.put(f"/api/tasks/{tid}",json={"title":"Updated","status":"done"},headers=h).status_code == 200
    other=app.test_client()
    oh=login(other,"bob")
    assert other.get("/api/projects",headers=oh).json["items"] == []
    for method,path,payload in [("get",f"/api/tasks?project_id={p}",None),("put",f"/api/tasks/{tid}",{"title":"Stolen"}),("delete",f"/api/projects/{p}",None),("post","/api/tasks",{"project_id":p,"title":"Injected"})]:
        assert getattr(other,method)(path,json=payload,headers=oh).status_code == 404
    assert c.put(f"/api/projects/{p}",json={"name":"Renamed"},headers=h).status_code == 200
    assert c.delete(f"/api/tasks/{tid}",headers=h).status_code == 200
    assert c.delete(f"/api/projects/{p}",headers=h).status_code == 200
    assert c.get(f"/api/tasks?project_id={p}",headers=h).status_code == 404


def test_invalid_credentials_tokens_and_payloads(app):
    c=app.test_client()
    h=login(c)
    assert c.post("/api/login",json={"username":"alice","password":"wrong"}).status_code == 401
    assert c.post("/api/projects",json={"name":" "},headers=h).status_code == 400
    assert c.post("/api/projects",json=[],headers=h).status_code == 400
    p=c.post("/api/projects",json={"name":"Test"},headers=h).json["id"]
    assert c.post("/api/tasks",json={"project_id":p,"title":"Bad","status":"invalid"},headers=h).status_code == 400
    assert c.get(f"/api/tasks?project_id={p}&page=0",headers=h).status_code == 400
    now=datetime.now(timezone.utc)
    token=jwt.encode({"sub":"1","iat":now-timedelta(hours=2),"exp":now-timedelta(hours=1),"iss":"task-platform"},app.config["SECRET_KEY"],algorithm="HS256")
    assert c.get("/api/projects",headers={"Authorization":"Bearer "+token}).status_code == 401
    assert c.get("/api/projects",headers={"Authorization":"Bearer invalid"}).status_code == 401
