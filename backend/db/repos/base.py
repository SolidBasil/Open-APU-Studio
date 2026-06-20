class RepoBase:
    def __init__(self, conn):
        self._conn = conn
        self._cursor = conn.cursor()

    def _uno(self, sql, params=None):
        row = self._cursor.execute(sql, params or []).fetchone()
        return dict(row) if row else None

    def _lista(self, sql, params=None):
        return [dict(r) for r in self._cursor.execute(sql, params or []).fetchall()]

    def _ejecutar(self, sql, params=None):
        self._cursor.execute(sql, params or [])
        self._conn.commit()
        return self._cursor.lastrowid

    def _muchos(self, sql, seq):
        self._cursor.executemany(sql, seq)
        self._conn.commit()
