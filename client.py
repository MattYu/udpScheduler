import socket
import sys
import model
import json
import threading
import collections
import queue
import sqlite3
import util
# REPLACE THIS WITH SERVER'S IP (Server IP printed when first executing 'python3 server.py')
host = '192.168.31.238'
#host = 'localhost'
port = 8888

class Client:



    def __init__(self, sessionName = "8000"):
        self.sessionName = sessionName
        self.lock = threading.Lock()
        self.running = True
        self.commandQueue = queue.Queue()
        self.ip = util.get_ip()
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except:
            print('Failed to create sockets')
            sys.exit()

        self.conn = sqlite3.connect(sessionName + "Client.db", check_same_thread=False)
        util.reset(self.conn)
        util.createBookingTable(self.conn)
        util.createParticipantTable(self.conn)
        util.createTrackingTable(self.conn)
        util.createClientInviteCacheTable(self.conn)
        util.createClientAcceptTable(self.conn)
        util.createClientRejectTable(self.conn)
        util.createClientRequestNumCacheTable(self.conn)

        try:
            currentRequestNum = self.conn.cursor().execute(
                '''
                SELECT * from requestNum
                '''
            ).fetchall()
            model.Request.requestNumber = len(currentRequestNum) + 1
        except Exception as e:
            print(e)
            pass
        #print("Length=" + str(model.Request.requestNumber))

        #self.startSender()
        self.startListener()
        self._menu(0, 0)

    def _menu(self, state, prevState, storedData =  {}):
        if (state == 0):
            print("****Main Menu*****")
            print("\tOption 1: Request a meeting")
            print("\tOption 2: Add a contact")
            print("\tOption 3: See all contacts")
            print("\tOption 4: See all confirmed meetings")
            print("\tOption 5: See all requested meetings")
            print("\tOption 6: Cancel a requested meeting")
            print("\tOption 7: Withdraw from a confirmed meeting")
            print("\tOption 8: Add a participant to a meeting")
            print("\tAt any time, enter 'Q' to return to the Main Menu.")
            print("\t'Exit' to turn off client")
            #print("\tOption 6: ")

            msg = input("Enter input: ")
            if (msg == "Exit"):
                self.running = False
                return
            if (msg.isdigit() and int(msg) > 0 and int(msg) <= 7):
                return self._menu(int(msg), state)
            else:
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState)
            

        if (state == 1):
            print("****Booking Menu*****")
            print("\tAt any time, enter 'Q' to return to the Main Menu.")
            msg = input("Meeting date [month]: ")
            if (msg == "Q"):
                return self._menu(0, 0)
            if (msg.isdigit() and int(msg) > 0 and int(msg) <= 12):
                storedData["month"] = msg
                return self._menu(8, state, storedData)
            else:
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState)

        if (state == 8):
            msg = input("Meeting date [day]: ")
            if (msg == "Q"):
                return self._menu(0, 0)
            if (msg.isdigit() and int(msg) > 0 and int(msg) <= 31):
                storedData["day"] = msg
                return self._menu(9, state, storedData)
            else:
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState, storedData)

        if (state == 9):
            msg = input("Meeting time [hour]: ")
            if (msg == "Q"):
                return self._menu(0, 0)
            if (msg.isdigit() and int(msg) > 0 and int(msg) <= 24):
                storedData["time"] = msg
                return self._menu(10, state, storedData)
            else:
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState, storedData)
        
        if (state == 10):
            print("****Select Participant from the list****")
            print("\tOption 0: Add a new participant")
            print("\te.g. if list contains 10 participant, enter '1,4,7' to invite participant 1, 4 and 7")
            participants = util.getParticipantList(self.conn)

            for row in participants:
                print("\tOption %s - IP: %s - Client Name: %s" % (row[0], row[1], row[2]))
            msg = input("Enter Input: ")
            if (msg == "0"):
                return self._menu(2, state, storedData)
            lists = msg.split(",")

            isValidInput = True
            for element in lists:
                if (element.isdigit() and int(element) > 0 and int(element) <= len(participants)):
                    continue
                else:
                    if (msg == "Q"):
                        return self._menu(0, 0)
                    print("****Invalid Command. Please try again")
                    return self._menu(state, prevState, storedData)

            storedData["participant"] = []
            for element in lists:
                storedData["participant"].append([participants[int(element)-1][1], participants[int(element)-1][2]])
            storedData["participant"].append([self.ip, self.sessionName])
            return self._menu(11, state, storedData)
            

        if (state == 11):
            msg = input("Enter minimum number of participant: ")
            if (msg == "Q"):
                return self._menu(0, 0)
            if (msg.isdigit() and int(msg) > 0 and int(msg) <= len(storedData["participant"])):
                storedData["minimum"] = int(msg)
                return self._menu(12, state, storedData)
            else:
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState, storedData)

        if (state == 12):
            msg = input("Enter meeting topic: ")

            try:
                seek = self.conn.cursor().execute(
                '''
                SELECT * from booking where date like ? and time like ? and status!="Cancelled" and status!="Non Scheduled"
                ''', (storedData["month"] + "-" + storedData["day"], storedData["time"])
                ).fetchall()

            except Exception as e:
                print(e)
                pass

            if (len(seek) > 0):
                print("****Warning:\n\tYou have accepted or requested a meeting at the same time.\n\tTo request this meeting, please cancel the previous meeting")
                return self._menu(0, 0)

            request = model.Request(storedData["month"] + "-" + storedData["day"], storedData["time"], storedData["minimum"], storedData["participant"], msg, self.sessionName)
            message = model.encode(request)
            print(message)

            try:
                self.conn.cursor().execute(
                    '''
                    INSERT INTO booking(date, time, meetingNumber, sourceIP, sourceClient, status, room, confirmedParticipant, topic, reason, min) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',(storedData["month"] + "-" + storedData["day"], storedData["time"], "unassigned", self.ip, self.sessionName, "sent", "no room yet", "", msg, "", "")
                )
                self.conn.cursor().execute(
                    '''
                    INSERT INTO requestNum(lastRequestNum) VALUES(?)
                    ''',(request.requestNumber,)
                )
            except Exception as e:
                print(e)
                pass

            msg = input("Press Any key to send above request")
            self._sender(message)
            return self._menu(0, 0)

        if (state == 2):
            print("****Enter new Participant****")
            msg = input("Participant IP: ")
            if (msg == "Q"):
                return self._menu(0, 0)
            participant = msg

            msg = input("Specific Client? [y/n]: ")

            if (msg == "n"):
                self.lock.acquire()
                util.addParticipant(self.conn, participant)
                self.lock.release()
                return self._menu(prevState, state, storedData)
            elif (msg == "y"):
                msg = input("Enter Client Name: ")
                self.lock.acquire()
                util.addParticipant(self.conn, participant, msg)
                self.lock.release()
                return self._menu(prevState, state, storedData)
            else:
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState, storedData)

        if (state == 4):
            self.lock.acquire()
            seek = self.conn.cursor().execute(
                '''
                SELECT* from booking where status="Confirmed" or status="Scheduled"
                '''
            ).fetchall()
            count = 1
            print("****Agenda****")
            print(len(seek))
            for row in seek:
                print("****")
                print(count)
                print(row)

            msg = input("Press Q to exit ")
            self.lock.release()
            if (msg == "Q"):
                return self._menu(0, 0)
            else:
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState, storedData)

        if (state == 6):
            seek = self.conn.cursor().execute(
                '''
                SELECT* from booking where status="Scheduled"
                '''
            ).fetchall()
            print("***Choose among the list which meeting you wish to cancel. Press 'Q' to return back\n")
            count = 0
            for row in seek:
                message = "\t[" + str(count) + "] " + str(row)
                print(message)

            msg = input("Enter a meeting number:")
            if (msg == "Q"):
                return self._menu(0, 0)
            elif (msg.isdigit() and int(msg) >= 0 and int(msg) < len(seek)):
                meetingNumber = seek[int(msg)][2]
                cancel = model.Cancel(meetingNumber, '', self.sessionName)
                storedData["message"] = model.encode(cancel)
                return self._menu(13, state, storedData)
            else:
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState)

        if (state == 13):
            print("****Are you sure?")
            msg = input("Y/N:")
            if (msg == "Y"):
                self._sender(storedData["message"])
                print("Sent")
                return self._menu(0, 0)
            if (msg == "N"):
                return self._menu(prevState, state, storeData)
            if (msg == "Q"):
                return self._menu(0, 0)
            else: 
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState, storedData)

        if (state == 7):
            seek = self.conn.cursor().execute(
                '''
                SELECT* from booking where status="Confirmed"
                '''
            ).fetchall()
            print("***Choose among the list which meeting you wish to withdraw from. Press 'Q' to return back\n")
            count = 0
            for row in seek:
                message = "\t[" + str(count) + "] " + str(row)
                print(message)

            msg = input("Enter a meeting number:")
            if (msg == "Q"):
                return self._menu(0, 0)
            elif (msg.isdigit() and int(msg) >= 0 and int(msg) < len(seek)):
                meetingNumber = seek[int(msg)][2]
                withdraw = model.Withdraw(meetingNumber, self.sessionName)
                storedData["message"] = model.encode(cancel)
                return self._menu(13, state, storedData)
            else:
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState)



    def startSender(self):
        threading.Thread(target=self._sender).start()

    def _sender(self, message):
        try :
            self.s.sendto(message.encode(), (host, port))
            
        except Exception as e:
            print(e)
            sys.exit()

    def startListener(self):
        threading.Thread(target=self._listener).start()

    def _listener(self):
        self.r.bind(('', int(self.sessionName)))
        self.r.setblocking(0)
        print("*****Current IP")
        print(self.ip)
        while (self.running):
            try:
                d = self.r.recvfrom(1024)
                data = d[0]
                addr = d[1]

                if (len(data) > 10):
                    self.startWorker(data, addr)
                #print('It worked! ' + str(data,'utf-8'))
            
            except (socket.error):
                pass
    def worker(self, data):
        data = str(data, 'utf-8')
    
    def autosave(self):
        return


    def startWorker(self, data, addr):
        threading.Thread(target=self._worker, args=(data,addr,)).start()

    def _worker(self, data, addr):
        data = str(data, 'utf-8')
        data = str(data).strip("'<>() ").replace('\'', '\"')
        print(data)
        print("\n")
        try:
            dataDict = model.decodeJson(data)
        except Exception as e:
            print("Error here:" + data)
            print(e)
            return


        if (dataDict.type == "Invite" and dataDict.targetName == self.sessionName):
            invite = dataDict
            # Check the cache to see if already responded to the same request before
            self.lock.acquire()
            try:
                seek = self.conn.cursor().execute(
                '''
                SELECT * from inviteCache where meetingNumber like ? and responseType like 'Accepted'
                ''', (invite.meetingNumber,)
                ).fetchall()

            except Exception as e:
                print("-5")
                print(e)
                pass
            if(len(seek) > 0):
                response = seek[0][1]
                self._sender(response)
                self.lock.release()
                return

            # Check if free slot is available 
            freeSlot = True
            try:
                seek = self.conn.cursor().execute(
                '''
                SELECT * from booking where date=? and time=? and status !="Cancelled" and status !="Non Scheduled"
                ''', (invite.date, invite.time)
                ).fetchall()

            except Exception as e:
                print("Something went wrong")
                print(e)
                pass
            if (len(seek) > 0):
                if (seek[0][3] == self.ip and seek[0][4] == self.sessionName and seek[0][5] == "sent"):
                    try:
                        seek = self.conn.cursor().execute(
                            '''
                            UPDATE booking SET meetingNumber=? where date=? and time=?
                            ''', (invite.meetingNumber, invite.date, invite.time)
                        )

                        seek = self.conn.cursor().execute(
                            '''
                            UPDATE booking SET status=? where date=? and time=?
                            ''', ("acknowledged", invite.date, invite.time)
                        )


                    except Exception as e:
                        print("-4")
                        print(e)
                        pass
                else:
                    self.conn.cursor().execute(
                        '''
                        INSERT INTO booking(date, time, meetingNumber, sourceIP, sourceClient, status, room, confirmedParticipant, topic, reason, min) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',(invite.date, invite.time, invite.meetingNumber, invite.requesterIP, invite.requesterName, "Refused", "", "", invite.topic, "Schedule conflict", "")
                    )
                    freeSlot = False
            else:
                try:
                    self.conn.cursor().execute(
                        '''
                        INSERT INTO booking(date, time, meetingNumber, sourceIP, sourceClient, status, room, confirmedParticipant, topic, reason, min) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',(invite.date, invite.time, invite.meetingNumber, invite.requesterIP, invite.requesterName, "Accepted", "no room yet", "", invite.topic, "", "")
                    )
                except Exception as e:
                    print("-4-1")
                    print(e)
                    pass

            message = ''
            if (freeSlot):
                accept = model.Accept(invite.meetingNumber,self.sessionName)
                message = model.encode(accept)
                try:
                    self.conn.cursor().execute(
                        '''
                        INSERT INTO accept(meetingNumber, date, time, status) VALUES (?, ?, ?, ?)
                        ''',(invite.meetingNumber, invite.date, invite.time, "sent")
                    )
                except Exception as e:
                    print("-3")
                    print(e)
                    pass

            else:
                reject = model.Reject(invite.meetingNumber,self.sessionName)
                message = model.encode(reject)
                try:
                    self.conn.cursor().execute(
                        '''
                        INSERT INTO reject(meetingNumber, date, time, status) VALUES (?, ?, ?, ?)
                        ''',(invite.meetingNumber, invite.date, invite.time, "sent")
                    )
                except Exception as e:
                    print("-2")
                    print(e)
                    pass
                
            try:
                responseType = "refused"
                if (freeSlot): 
                    responseType = "Accepted"
                self.conn.cursor().execute(
                    '''
                    INSERT INTO inviteCache(invite, prevResponse, meetingNumber, responseType) VALUES (?, ?, ?, ?)
                    ''', (data, message, invite.meetingNumber, responseType)
                )
            except Exception as e:
                print("-1")
                print(e)
                pass
            util.commit(self.conn)
            self.lock.release()
            self._sender(message)

        if (dataDict.type == "Confirm" or dataDict.type == "Cancel" or dataDict.type == "Scheduled" or dataDict.type == "Non_Scheduled"):
            print("R******R")
            meetingStatus = dataDict
            status = ""
            reason = ""
            room = ""
            self.lock.acquire()
            if (dataDict.type == "Confirm"):
                status = "Confirmed"
                room = meetingStatus.room
            elif (dataDict.type == "Cancel"):
                status = "Cancelled"
                reason = meetingStatus.reason
            elif (dataDict.type == "Scheduled"):
                status = "Scheduled"
                room = meetingStatus.room
            else:
                status = "Non Scheduled"
                reason = "Insufficient number of accepted participants/Or room was booked"

            try:
                seek = self.conn.cursor().execute(
                '''
                SELECT * from booking where meetingNumber =? 
                ''', (meetingStatus.meetingNumber,)
                ).fetchall()
            except Exception as e:
                print(e)
                pass

            if (len(seek)>0):
                print("P*******P")
                print(reason)
                print(status)
                print(meetingStatus.meetingNumber)
                try:
                    '''
                    self.conn.cursor().execute(
                        
                        UPDATE booking SET status=? and reason=? and room=? where meetingNumber=?
                        , (status, reason, room, str(meetingStatus.meetingNumber))
                    )
                    '''
                    self.conn.cursor().execute(
                        '''
                        UPDATE booking SET status=? where meetingNumber=?
                        ''', (status, meetingStatus.meetingNumber)
                    )

                    self.conn.cursor().execute(
                        '''
                        UPDATE booking SET reason=? where meetingNumber=?
                        ''', (reason, meetingStatus.meetingNumber)
                    )

                    self.conn.cursor().execute(
                        '''
                        UPDATE booking SET room=? where meetingNumber=?
                        ''', (room, meetingStatus.meetingNumber)
                    )

                except Exception as e:
                    print(e)
                    pass
                util.commit(self.conn)
                if (dataDict.type == "Scheduled" or dataDict.type == "Non_Scheduled"):
                    self.conn.cursor().execute(
                        '''
                        UPDATE booking SET confirmedParticipant=? where meetingNumber=?
                        ''', (''.join(str(e) for e in meetingStatus.listConfirmedParticipant), meetingStatus.meetingNumber)
                    )
                    util.commit(self.conn)
                    if (dataDict.type == "Non_Scheduled"):
                        self.conn.cursor().execute(
                            '''
                            UPDATE booking SET min=? where meetingNumber=?
                            ''', (meetingStatus.minimum, meetingStatus.meetingNumber)
                        )
                    util.commit(self.conn)
                if (dataDict.type == "Accept"):
                    self.conn.cursor().execute(
                        '''
                        UPDATE accept SET status=? where meetingNumber=?
                        ''', ("received", meetingStatus.meetingNumber)
                    )
                    self.conn.cursor().execute(
                        '''
                        UPDATE reject SET status=? where meetingNumber=?
                        ''', ("received", meetingStatus.meetingNumber)
                    )

                if (dataDict.type == "Cancel"):
                    self.conn.cursor().execute(
                        '''
                        UPDATE accept SET status=? where meetingNumber=?
                        ''', ("received", meetingStatus.meetingNumber)
                    )
                    self.conn.cursor().execute(
                        '''
                        UPDATE reject SET status=? where meetingNumber=?
                        ''', ("received", meetingStatus.meetingNumber)
                    )
                if (dataDict.type == "Cancel" or dataDict.type == "Non_Scheduled"):
                    # Can now accept another meeting at the same time slot. Attempt to find a previously refused meeting 

                    seek =  self.conn.cursor().execute(
                        '''
                        SELECT* from booking where meetingNumber=?
                        ''', (meetingStatus.meetingNumber,)
                    ).fetchall()

                    date = seek[0][0]
                    time = seek[0][1]

                    # Find another previous refused meeting at the same date and time and accept it if one is found

                    seek =  self.conn.cursor().execute(
                        '''
                        SELECT* from booking where date=? and time=? and status="Refused"
                        ''', (date,time)
                    ).fetchall()


                    if (len(seek)>0):
                        newMeetingNumber = seek[0][2]

                        add = model.Add(newMeetingNumber,self.sessionName)
                        message = model.encode(add)

                        self.conn.cursor().execute(
                        '''
                        UPDATE booking SET status =? where meetingNumber=?
                        ''', ("Accepted", newMeetingNumber)
                        )
                        try:
                            self.conn.cursor().execute(
                                '''
                                INSERT INTO accept(meetingNumber, date, time, status) VALUES (?, ?, ?, ?)
                                ''',(newMeetingNumber, date, time, "sent")
                            )
                        except Exception as e:
                            print(e)
                            pass

                        self._sender(message)
            util.commit(self.conn)
            self.lock.release()
            

if (len(sys.argv) > 1):
    Client(sys.argv[1])
else:
    Client()

'''
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
except (socket.error):
    print('Failed to create socket')
    sys.exit()
 
host2 = 'localhost'
port = 8888

loop = True

while(loop) :
    msg = input("Enter input: ")
    print(msg)

    if (msg == "exit"):
        loop = False
     
    try :
        s.sendto(msg.encode(), (host2, port))
         
        d = s.recvfrom(1024)
        reply = d[0]
        addr = d[1]

         
        print('Server reply : ' + str(reply,'utf-8'))
     
    except Exception as e:
        print(e)
        sys.exit()

s.close()
'''