import socket
import sys
import model
import json
import threading
import collections
import queue
import sqlite3
import util

HOST = ''
PORT = 8888

class Server:

    def __init__(self, numberOfMeetingRoom):
        self.meetingRoomNum = numberOfMeetingRoom
        self.lock = threading.Lock()
        self.ip = util.get_ip()
        self.conn = sqlite3.connect("Server.db", check_same_thread=False)
        util.reset(self.conn)
        util.createServerBookingTable(self.conn)
        util.createServerRecevedRequestTable(self.conn)
        util.createServerInviteTable(self.conn)
        util.createServerInviteListTable(self.conn)
        util.createServerMeetingNumCacheTable(self.conn)
        try:
            currentMeetingNum = self.conn.cursor().execute(
                '''
                SELECT * from meetingNum
                '''
            ).fetchall()
            model.Invite.meetingNumber = len(currentMeetingNum) + 1
        except Exception as e:
            print(e)
            pass

        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.s.bind((HOST, PORT))
            print("Socket created")
        except Exception as e:
            print(e)
            sys.exit()
        

        self.running = True
        #self._menu(0,0)
        self.startListner()
        self.startMenu()
        print("Server is running")

    def startMenu(self):
        threading.Thread(target=self._menu, args=(0,0,)).start()

    def _menu(self, state, prevState, storedData =  {}):
        if (state == 0):
            print("\t****Server Main Menu*****")
            print("\t'Exit' to turn off server")

            msg = input("\tEnter input: ")
            if (msg == "Exit"):
                self.running = False
                return
            if (msg.isdigit() and int(msg) > 0 and int(msg) <= 0):
                return self._menu(int(msg), state)
            else:
                print("\t****Invalid Command. Please try again")
                return self._menu(state, prevState)

    def startListner(self):
        threading.Thread(target=self._listener).start()

    def _listener(self):
        while (self.running):
            d = self.s.recvfrom(1024)
            data = d[0]
            addr = d[1]

            if not data: 
                break
            
            self.startWorker(data, addr)

        self.s.close()

    def startWorker(self, data, addr):
        threading.Thread(target=self._worker, args=(data,addr,)).start()

    def _worker(self, data, addr):
        data = str(data, 'utf-8')
        print("\n")
        dataDict = json.loads(data)

        if (dataDict["type"] == "Request"):
            request = model.decodeJson(data)
            # Check the cache to see if already responded to the same request before
            self.lock.acquire()
            try:
                seek = self.conn.cursor().execute(
                '''
                SELECT * from request where requestNumber like ? and IP like ? and client like ?
                ''', (request.requestNumber, str(addr[0]), request.requestClientName)
                ).fetchall()

            except Exception as e:
                print(e)
                pass
            if(len(seek) > 0):
                print("deja vu")
                response = seek[0][1]
                self.s.sendto(response.encode(), (addr[0], int(request.requestClientName)))
                self.lock.release()
                return

            # Check if free slot is available 
            freeSlot = True
            try:
                seek = self.conn.cursor().execute(
                '''
                SELECT * from booked where date=? and time=?
                ''', (request.date, request.time)
                ).fetchall()

            except Exception as e:
                print("Something went wrong")
                print(e)
                pass

 
            message = ""
            if (len(seek) > self.meetingRoomNum):
                response = util.Response(request.requestNumber, request.requestClientName, "No room available")
                message = model.encode(response)
                try:
                    self.s.sendto(message.encode(), (addr[0], int(request.requestClientName)))
                except Exception as e:
                    print(e)
                    pass
            else:
                invite = model.Invite(request.date, request.time, request.topic, addr[0], request.requestClientName, request.requestClientName)

                try:
                    self.conn.cursor().execute(
                        '''
                        INSERT INTO meetingNum(lastMeetingNum) VALUES (?)
                        ''', (invite.meetingNumber,)
                    )

                    self.conn.cursor().execute(
                        '''
                        INSERT INTO invite(meetingNumber, invite, min, confirmed) VALUES (?, ?, ?, ?)
                        ''', (invite.meetingNumber, model.encode(invite), request.minimum, 0)
                    )

                except Exception as e:
                    print(e)
                    pass

                for participant in request.participant:
                    invite.targetName = participant[1]
                    message = model.encode(invite)
                    print("Comparison:" + participant[0] + "vs" + addr[0])
                    try:
                        self.s.sendto(message.encode(), (participant[0], int(invite.targetName)))
                    except Exception as e:
                        print(e)
                        pass
                    try:
                        self.conn.cursor().execute(
                            '''
                            INSERT INTO inviteList(meetingNumber, ip, client, status) VALUES (?, ?, ?, ?)
                            ''', (invite.meetingNumber, participant[0], participant[1], "Sent")
                        )
                    except Exception as e:
                        print(e)
                        pass


            self.conn.cursor().execute(
                '''
                INSERT INTO request(request, prevResponse, IP, client, requestNumber) VALUES (?, ?, ?, ?, ?)
                ''', (data, message, addr[0], request.requestClientName, request.requestNumber)
            )
            util.commit(self.conn)
            self.lock.release()

        if (dataDict["type"] == "Accept" or dataDict["type"] == "Reject"):
            print("it works!!")
            print(addr)
            print(data)
        
        #self.s.sendto(("testss").encode(), (addr[0], 8000))



Server(1)