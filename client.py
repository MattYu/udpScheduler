import socket
import sys
import model
import json
import threading
import collections
import queue
import sqlite3
import util
import tkinter as tk
import time
import logging
from view import *
# REPLACE THIS WITH SERVER'S IP (Server IP printed when first executing 'python3 server.py')
host = '192.168.31.238'
#host = 'localhost'
port = 8888

class Client:

    def __init__(self, sessionName = "8000"):
        self.host = host
        self.sessionName = sessionName
        self.lock = threading.Lock()
        self.running = True
        self.commandQueue = queue.Queue()
        self.ip = util.get_ip()

        logging.basicConfig(filename=sessionName + "_log.txt",
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except:
            print('Failed to create sockets')
            sys.exit()

        self.conn = sqlite3.connect(sessionName + "Client.db", check_same_thread=False)
        #util.reset(self.conn)
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
        #self._menu(0, 0)
        #root = tk.Tk()
        #root.title("UDP Scheduler2")
        #set_nb(root)
        self.mainView = MainView()
        self.mainView.execute(self)
        #main.pack(side="top", fill="both", expand=True)
        root.mainloop()
        self.running = False

    def startSender(self):
        threading.Thread(target=self._sender).start()

    def messageAckWatchdog(self):
        threading.Thread(target=self.resendMessage).start()

    def resendMessage(self):
        while (self.running):
            notAckList = self.conn.cursor().execute(
            '''
            SELECT * FROM accept where status!='sent'
            '''
            ).fetchall()

            notAckRequest = self.conn.cursor().execute(
            '''
            SELECT * FROM booking where status!='sent'
            '''
            ).fetchall()

            time.sleep(100)
            for sentAccept in notAckList:
                meetingNumber = sentAccept[0]
                message = sentAccept[4]
                ackCheck = self.conn.cursor().execute(
                '''
                SELECT * FROM accept where meetingNumber=? and status="Sent"
                ''', (meetingNumber,)
                ).fetchall()

                if (len(ackCheck) !=0):
                    self._sender(message)
            

    def _sender(self, message):
        try :
            logging.info("\nSending:" + str(message) + " to " + str((host, port)))
            self.r.sendto(message.encode(), (host, port))
            
        except Exception as e:
            print(e)
            sys.exit()

    def startListener(self):
        threading.Thread(target=self._listener).start()

    def _listener(self):
        self.r.bind(('', int(self.sessionName)))
        self.r.setblocking(0)
        #print("*****Current IP")
        #print(self.ip)
        while (self.running):
            try:
                d = self.r.recvfrom(1024)
                data = d[0]
                addr = d[1]

                if (len(data) > 10):
                    logging.info("\nReceived:" + str(data, 'utf-8') + " from " + str(addr))
                    self.startWorker(data, addr)
                #print('It worked! ' + str(data,'utf-8'))
            
            except (socket.error):
                pass
        self.s.close()
        self.r.close()
        
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
                SELECT * from booking where date=? and time=? and status !="Cancelled" and status !="Non Scheduled" and status!="Withdrawn"
                ''', (invite.date, invite.time)
                ).fetchall()

            except Exception as e:
                print("-6")
                print(e)
                pass
            if (len(seek) > 0):
                if (seek[0][3] == self.ip and seek[0][4] == self.sessionName and seek[0][5] == "sent"):
                    try:
                        seek = self.conn.cursor().execute(
                            '''
                            UPDATE booking SET meetingNumber=? where date=? and time=? and status !="Cancelled" and status !="Non Scheduled" and status!="Withdrawn"
                            ''', (invite.meetingNumber, invite.date, invite.time)
                        )

                        seek = self.conn.cursor().execute(
                            '''
                            UPDATE booking SET status=? where date=? and time=? and meetingNumber=?
                            ''', ("acknowledged", invite.date, invite.time, invite.meetingNumber)
                        )


                    except Exception as e:
                        print("-4")
                        print(e)
                        pass
                else:
                    #print("*************************!!!!!!!!!!!!!!!*****************************")
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
                        INSERT INTO accept(meetingNumber, date, time, status, message) VALUES (?, ?, ?, ?, ?)
                        ''',(invite.meetingNumber, invite.date, invite.time, "sent", message)
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
            #print("R******R")
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
                #print("P*******P")
                #print(reason)
                #print(status)
                #print(meetingStatus.meetingNumber)
                try:
                    '''
                    self.conn.cursor().execute(
                        
                        UPDATE booking SET status=? and reason=? and room=? where meetingNumber=?
                        , (status, reason, room, str(meetingStatus.meetingNumber))
                    )
                    '''
                    self.conn.cursor().execute(
                        '''
                        UPDATE booking SET status=? where meetingNumber=? and status!="Cancelled"
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
                                INSERT INTO accept(meetingNumber, date, time, status, message) VALUES (?, ?, ?, ?, ?)
                                ''',(newMeetingNumber, date, time, "sent", message)
                            )
                        except Exception as e:
                            print(e)
                            pass

                        self._sender(message)
            util.commit(self.conn)
            self.lock.release()
        
        if (dataDict.type == "Withdraw"):
            # Update meeting Participant list
            withdraw = dataDict
            meetingNumber = withdraw.meetingNumber
            withdrawerIP = withdraw.clientIP
            withdrawerPort = withdraw.clientName

            agenda = self.conn.cursor().execute(
                '''
                    SELECT * from booking where meetingNumber=?
                ''', (meetingNumber,)
            ).fetchall()

            if (len(agenda)!=0):
                participants = agenda[0][7][1:-1] + "]"
                participants = "[" + participants + str(["Withdrawal:" + withdrawerIP, withdrawerPort])

                print(participants)

                self.conn.cursor().execute(
                    '''
                        UPDATE booking SET confirmedParticipant=? where meetingNumber=?
                    ''', (str(participants), meetingNumber)
                )


        if (dataDict.type == "Room_Change"):
            roomChange = dataDict

            meetingNumber = roomChange.meetingNumber
            newRoom = roomChange.newRoom
            self.lock.acquire()
            self.conn.cursor().execute(
            '''
            UPDATE booking SET room =? where meetingNumber=?
            ''', (newRoom, meetingNumber)
            )
            self.lock.release()

        
        self.mainView.refreshUI()

if (len(sys.argv) > 1):
    Client(sys.argv[1])
    if (len(sys.argv) > 2):
        host = sys.argv[2]
else:
    Client()