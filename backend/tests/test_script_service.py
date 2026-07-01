import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from app.services.script_service import list_scripts, get_script, create_script, update_script, delete_script
from app.schemas.script import ScriptCreate, ScriptUpdate


class TestScriptService:
    def test_create_and_get(self, db_session):
        data = ScriptCreate(name="svc-test", type="shell", content="echo ok", timeout=30)
        s = create_script(db_session, data)
        assert s.id > 0
        assert s.name == "svc-test"

        fetched = get_script(db_session, s.id)
        assert fetched is not None
        assert fetched.name == "svc-test"

    def test_update_script(self, db_session):
        data = ScriptCreate(name="svc-test", type="shell", content="echo ok", timeout=30)
        s = create_script(db_session, data)
        updated = update_script(db_session, s, ScriptUpdate(name="renamed"))
        assert updated.name == "renamed"

    def test_delete_script(self, db_session):
        data = ScriptCreate(name="to-delete", type="shell", content="x", timeout=30)
        s = create_script(db_session, data)
        sid = s.id
        delete_script(db_session, s)
        assert get_script(db_session, sid) is None

    def test_list_empty(self, db_session):
        result = list_scripts(db_session)
        assert result["total"] == 0

    def test_list_with_items(self, db_session):
        for i in range(3):
            create_script(db_session, ScriptCreate(name=f"s{i}", type="shell", content="x", timeout=30))
        result = list_scripts(db_session, page=1, page_size=2)
        assert result["total"] == 3
        assert len(result["items"]) == 2

    def test_list_search(self, db_session):
        create_script(db_session, ScriptCreate(name="alpha", type="shell", content="x", timeout=30))
        create_script(db_session, ScriptCreate(name="beta", type="shell", content="x", timeout=30))
        result = list_scripts(db_session, search="alp")
        assert result["total"] == 1
        assert result["items"][0].name == "alpha"
