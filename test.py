import sqlite3
import util

conn = sqlite3.connect("server.db")

def tableExists(conn, tableName):
    cur = conn.cursor()
    cur.execute("""
    SELECT count(*)
    FROM sqlite_master 
    WHERE type ='table'
    AND
    name ='{0}'
    """.format(tableName.replace('\'', '\'\'')))

    res = False
    if cur.fetchone()[0] == 1:
        res = True
    cur.close()
    return res

util.createServerRecevedRequestTable(conn)
print(tableExists(conn, "request"))