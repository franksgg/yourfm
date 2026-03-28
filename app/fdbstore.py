import json
import datetime
from web import session
from indexer import indexmedia
from fdb import TransactionContext


class FBStore(session.Store):
    """Store for saving a session in a firbird  database
    Needs a table with the following columns:

        session_id CHAR(128) UNIQUE NOT NULL,
        atime DATETIME NOT NULL default current_timestamp,
        data TEXT
    """

    def query_db(self, query, args=(), one=False):
        #connection = indexmedia.get_connector()
        #self.db = connection.getconnection()
        with TransactionContext(self.db.trans()) as tr:
            cur = tr.cursor()
            cur.execute(query, args)
            r = cur.fetchone() if one else cur.fetchall()
            tr.commit()
        return r if r else None

    def exec_db(self, query, args=()):
        #connection = indexmedia.get_connector()
        #self.db = connection.getconnection()
        with TransactionContext(self.db.trans()) as tr:
            cur = tr.cursor()
            cur.execute(query, args)
            tr.commit()
        return cur.rowcount

    def __init__(self, db, table_name):
        self.db = db
        self.table = table_name

    def __contains__(self, key):
        data = self.query_db("select * from " + self.table + " where session_id=?", (key,))
        try:
            return bool(list(data))
        except:
            return False

    def __getitem__(self, key):
        now = datetime.datetime.now()
        try:
            s = self.query_db("select data from " + self.table + " where session_id=?", (key,), True)[0]
            try:
                self.exec_db("update " + self.table + " set atime=? where session_id=?", (now, key,))
            except:
                pass
        except IndexError:
            raise KeyError
        else:
            return self.decode(s)

    def __setitem__(self, key, value):
        pickled = self.encode(value)
        cvalue = json.dumps(value)
        now = datetime.datetime.now()
        if key in self:
            try:
                self.exec_db("update " + self.table + " set data2=?,data=?,atime=? where session_id=?",
                             (cvalue, pickled, now, key,))
            except:
                pass
        else:
            try:
                self.exec_db("insert into " + self.table + " (SESSION_ID, ATIME, data, data2) values (?, ?, ?, ? )",
                             (key, now, pickled, cvalue,))
            except:
                pass

    def __delitem__(self, key):
        self.exec_db("delete from " + self.table + "  where session_id = atime", (key,))

    def cleanup(self, timeout):
        timeout = datetime.timedelta(timeout / (24.0 * 60 * 60))  # timedelta takes numdays as arg
        last_allowed_time = datetime.datetime.now() - timeout
        self.exec_db("delete from " + self.table + "  where ? > atime", (last_allowed_time,))
