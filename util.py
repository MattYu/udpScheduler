import sqlite3
import socket

def get_ip():
    #From stackoverflow https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def commit(conn):
    conn.commit()

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

def createClientRequestNumCacheTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            requestNum(lastRequestNum INTEGER NOT NULL)
            '''
        )
    except:
        pass

def createServerMeetingNumCacheTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            meetingNum(lastMeetingNum INTEGER NOT NULL)
            '''
        )
    except:
        pass

def createClientAcceptTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            accept(meetingNumber INTEGER NOT NULL, date VARCHAR(25) NOT NULL, time VARCHAR(25) NOT NULL, status VARCHAR(25) NOT NULL, message VARCHAR(1000) NOT NULL)
            '''
        )
    except:
        pass

def createClientRejectTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            reject(meetingNumber INTEGER NOT NULL, date VARCHAR(25) NOT NULL, time VARCHAR(25) NOT NULL, status VARCHAR(25) NOT NULL)
            '''
        )
    except:
        pass


def createServerInviteTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            invite(meetingNumber INTEGER NOT NULL, invite VARCHAR(500) NOT NULL, min INTEGER NOT NULL)
            '''
        )
    except:
        pass

def createServerInviteListTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            inviteList(meetingNumber INTEGER NOT NULL, ip VARCHAR(25) NOT NULL, client VARCHAR(25) NOT NULL, status VARCHAR(25) NOT NULL, message VARCHAR(1000) NOT NULL)
            '''
        )
    except:
        pass


def createServerBookingTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            booked(date VARCHAR(25) NOT NULL, time INTEGER NOT NULL, meetingId INTEGER NOT NULL, status VARCHAR(25) NOT NULL, room VARCHAR(3) NOT NULL)
            '''
        )
    except:
        pass

def createServerMeetingNumberToRoom(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            meetingToRoom(meetingNumber INTEGER NOT NULL, room INTEGER NOT NULL)
            '''
        )
    except:
        pass

def createClientInviteCacheTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            inviteCache(invite VARCHAR(500) NOT NULL, prevResponse VARCHAR(500) NOT NULL, meetingNumber INTEGER NOT NULL, responseType VARCHAR(10) NOT NULL)
            '''
        )
    except Exception as e:
        print(e)
        pass

def createServerRecevedRequestTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            request(request VARCHAR(500) NOT NULL, prevResponse VARCHAR(500) NOT NULL, IP VARCHAR(25) NOT NULL, client VARCHAR(25) NOT NULL, requestNumber INTEGER NOT NULL, meetingNumber INTEGER NOT NULL)
            '''
        )
    except Exception as e:
        print(e)
        pass


def createBookingTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            booking(date VARCHAR(25) NOT NULL, time INTEGER NOT NULL, meetingNumber VARCHAR(25) NOT NULL, sourceIP VARCHAR(25) NOT NULL, sourceClient VARCHAR(25) NOT NULL, status VARCHAR(25) NOT NULL, room VARCHAR(25) NOT NULL, confirmedParticipant VARCHAR(25) NOT NULL, topic VARCHAR(25) NOT NULL, reason VARCHAR(100) NOT NULL, min VARCHAR(25) NOT NULL)
            '''
        )
    except:
        pass

def createTrackingTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            tracking(p_id INTEGER PRIMARY KEY, type VARCHAR(25) NOT NULL, status VARCHAR(25) NOT NULL, message VARCHAR(500) NOT NULL)
            '''
        )
    except:
        pass

def addTaskToTracker(conn, t, status, message):
    try:
        conn.cursor().execute('INSERT INTO tracking(type, status, message) VALUES (?, ?, ?)', (t, status, message))
        conn.commit()
    except Exception as e:
        print(e)
        pass

def createParticipantTable(conn):
    try:
        conn.cursor().execute(
            '''
            CREATE TABLE IF NOT EXISTS 
            participant(p_id INTEGER PRIMARY KEY, ip VARCHAR(25) NOT NULL, clientName VARCHAR(25) NOT NULL)
            '''
        )
    except:
        pass

def getParticipantList(conn):
    try:
        res = conn.cursor().execute(
            '''
            SELECT * from participant
            '''
        ).fetchall()

        return res
    except Exception as e:
        print(e)
        pass

def getConfirmedList(conn):
    try:
        res = conn.cursor().execute(
        '''
        SELECT* from booking where status="Confirmed"
        '''
        ).fetchall()

        return res

    except Exception as e:
        print(e)
        pass

def getScheduledList(conn):
    try:
        res = conn.cursor().execute(
            '''
            SELECT* from booking where status="Scheduled"
            '''
        ).fetchall()

        return res
    except Exception as e:
        print(e)
        pass

def getEntireList(conn):
    try:
        res = conn.cursor().execute(
            '''
            SELECT* from booking
            '''
        ).fetchall()

        return res
    except Exception as e:
        print(e)
        pass   

def addParticipant(conn, ip, clientName = "8000"):
    try:
        conn.cursor().execute('INSERT INTO participant(ip, clientName) VALUES (?, ?)', (ip, clientName))
        conn.commit()
    except Exception as e:
        print(e)
        pass
        

def reset(conn):
    try:
        '''
        conn.cursor().execute(
            "DROP TABLE IF EXISTS participant"
        )
        '''
        conn.cursor().execute(
            "DROP TABLE IF EXISTS booking"
        )
        conn.cursor().execute(
            "DROP TABLE IF EXISTS tracking"
        )
        conn.cursor().execute(
            "DROP TABLE IF EXISTS invite"
        )
        conn.cursor().execute(
            "DROP TABLE IF EXISTS inviteCache"
        )
        conn.cursor().execute(
            "DROP TABLE IF EXISTS inviteList"
        )
        conn.cursor().execute(
            "DROP TABLE IF EXISTS request"
        )
        conn.cursor().execute(
            "DROP TABLE IF EXISTS booked"
        )
        conn.cursor().execute(
            "DROP TABLE IF EXISTS invite"
        )
        conn.cursor().execute(
            "DROP TABLE IF EXISTS accept"
        )
        conn.cursor().execute(
            "DROP TABLE IF EXISTS reject"
        )
        
        conn.cursor().execute(
            "DROP TABLE IF EXISTS requestNum"
        )
        
        conn.cursor().execute(
            "DROP TABLE IF EXISTS meetingNum"
        )

        conn.cursor().execute(
            "DROP TABLE IF EXISTS meetingToRoom"
        )

        
    except Exception as e:
        print(e)
        pass


'''
conn = sqlite3.connect("client.db")
reset(conn)
c = conn.cursor()
createBookingTable(conn)
createParticipantTable(conn)
addParticipant(conn, "111111")
addParticipant(conn, "222222", "testClient")
result = getParticipantList(conn)

for row in result:
    print(row)
print(result)
print(tableExists(conn, "participant"))
reset(conn)
'''