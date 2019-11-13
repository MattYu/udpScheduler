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
            self.s.setblocking(0)

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
            try:
                d = self.s.recvfrom(1024)
            except (socket.error):
                continue
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
        print(addr)
        print(data)

        ###################################
        # Request Handler
        ###################################
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
                if (seek[0][0] == data):
                    print("Message deja vu")
                    response = seek[0][1]
                    self.s.sendto(response.encode(), (addr[0], int(request.requestClientName)))
                else:
                    print("Invalid message")
                    response = model.Response(request.requestNumber, request.requestClientName, "The request number has been previously used for another message")
                    response = model.encode(response)
                    self.s.sendto(response.encode(), (addr[0], int(request.requestClientName)))
                self.lock.release()
                return

            # Check if free slot is available, respond accordingly and update cache
            freeSlot = True
            try:
                seek = self.conn.cursor().execute(
                '''
                SELECT * from booked where date=? and time=? and status!='Cancelled'
                ''', (request.date, request.time)
                ).fetchall()

            except Exception as e:
                print("Something went wrong")
                print(e)
                pass

            meetingNumber = -1
            message = ""
            if (len(seek) > self.meetingRoomNum):
                response = model.Response(request.requestNumber, request.requestClientName, "No room available")
                message = model.encode(response)
                try:
                    self.s.sendto(message.encode(), (addr[0], int(request.requestClientName)))
                except Exception as e:
                    print(e)
                    pass
            else:
                invite = model.Invite(request.date, request.time, request.topic, addr[0], request.requestClientName, request.requestClientName)
                meetingNumber = invite.meetingNumber
                try:
                    self.conn.cursor().execute(
                        '''
                        INSERT INTO meetingNum(lastMeetingNum) VALUES (?)
                        ''', (invite.meetingNumber,)
                    )

                    self.conn.cursor().execute(
                        '''
                        INSERT INTO invite(meetingNumber, invite, min) VALUES (?, ?, ?)
                        ''', (invite.meetingNumber, model.encode(invite), request.minimum)
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
                INSERT INTO request(request, prevResponse, IP, client, requestNumber, meetingNumber) VALUES (?, ?, ?, ?, ?, ?)
                ''', (data, message, addr[0], request.requestClientName, request.requestNumber, meetingNumber)
            )
            util.commit(self.conn)
            self.lock.release()

        ###################################
        # Accept or Reject handler
        ###################################
        if (dataDict["type"] == "Accept" or dataDict["type"] == "Reject"):
            # Note that a client will continuously ping the server (send its accept meeting or reject meeting message every 5 seconds) until it receves either a cancel, confirm, scheduled or not_scheduled message from the server

            acceptOrReject = model.decodeJson(data)
            
            # Does the referred meeting exists?
            self.lock.acquire()
            invite = self.conn.cursor().execute(
                '''
                    SELECT * from invite where meetingNumber=?
                ''', (acceptOrReject.meetingNumber, )
            ).fetchall()
            # If the client sent us a meeting number that does not exist in the system, we'll send a cancel message to avoid getting continuously pinged by the client instead of ignoring it
            if (len(invite) == 0):
                message = model.Cancel(acceptOrReject.meetingNumber, "Meeting does not exits")
                response = model.encode(message)
                self.s.sendto(response.encode(), (addr[0], int(acceptOrReject.clientName)))
                self.lock.release()
                return

            if (len(invite) > 0):
                
                # Was this message sent from someone invited to the referred meeting? 
                inviteList = self.conn.cursor().execute(
                    '''
                        SELECT * from inviteList where meetingNumber=? and ip=? and client=?
                    ''', (acceptOrReject.meetingNumber, addr[0], acceptOrReject.clientName)
                ).fetchall()
                # If the client is not invited to the meeting, we'll send a cancel message to avoid getting continuously pinged by the client instead of ignoring it
                if (len(inviteList) == 0):
                    print("Participant was not invited")
                    message = model.Cancel(acceptOrReject.meetingNumber, "You are not invited to this meeting")
                    response = model.encode(message)
                    self.s.sendto(response.encode(), (addr[0], int(acceptOrReject.clientName)))
                    self.lock.release()
                    return

                # Is the invitee responding for the first time? If not, do not count the message in the tally. If a client sends two different messages for the same meeting invite, only the first will count
                if (inviteList[0][3] == "Sent"):
                    if (acceptOrReject.type == "Accept"):
                        self.conn.cursor().execute(
                            '''
                            UPDATE inviteList SET status=? where meetingNumber=? and ip=? and client=?
                            ''', ("Accepted", acceptOrReject.meetingNumber, addr[0], acceptOrReject.clientName)
                        )
                    else:
                        self.conn.cursor().execute(
                            '''
                            UPDATE inviteList SET status=? where meetingNumber=? and ip=? and client=?
                            ''', ("Refused", acceptOrReject.meetingNumber, addr[0], acceptOrReject.clientName)
                        )

                # What's the total number of invitees for this meeting? (Without counting the participants who withdrew from the meeting)
                totalInvites = self.conn.cursor().execute(
                    '''
                    SELECT COUNT(*) from inviteList where meetingNumber=? and status!='withdrawn'
                    ''',(acceptOrReject.meetingNumber,)
                ).fetchone()[0]


                # How many accepted so far?
                totalAcceptedSoFar = self.conn.cursor().execute(
                    '''
                    SELECT COUNT(*) from inviteList where meetingNumber=? and status='Accepted'
                    ''',(acceptOrReject.meetingNumber,)
                ).fetchone()[0]

                # How many refused so far?
                totalRefusedSoFar = self.conn.cursor().execute(
                    '''
                    SELECT COUNT(*) from inviteList where meetingNumber=? and status='Refused'
                    ''',(acceptOrReject.meetingNumber,)
                ).fetchone()[0]

                # Based on the current accepted or refused tally, can the meeting still happen?

                minThreshold = invite[0][2]
        
                howManyCanStillAccept = totalInvites - totalRefusedSoFar

                # If insufficient responses to come to a conclusion, we stop here and wait for more responses and do nothing for now
                '''
                if (totalAcceptedSoFar < minThreshold and howManyCanStillAccept >= minThreshold):
                    self.lock.release()
                    return
                '''
                # Pass this point, we have enough response to make a decision

                originalInvite = model.decodeJson(invite[0][1])
                requesterIP = originalInvite.requesterIP
                requesterPort = originalInvite.requesterName
                # Note that since the scheduler works on a first come first served basis, while it guarantees a room was free at the time the request was made, by the time the meeting gets confirmed, another request might have taken the room
                # If that happens, we will send a cancel message instead
                freeSlot = True
                try:
                    seek = self.conn.cursor().execute(
                    '''
                    SELECT * from booked where date=? and time=? and status!='Cancelled' and meetingId!=?
                    ''', (originalInvite.date, originalInvite.time, originalInvite.meetingNumber)
                    ).fetchall()
                except Exception as e:
                    print("Something went wrong")
                    print(e)
                    pass
                if (len(seek) > self.meetingRoomNum):
                    Print("No more roomm available")
                    freeSlot = False

                # If we have reached the min participant threshold for the first, we will batch send messages to all those who have previously accepted the invite
                # The original meeting creator will get a slightly different conformation than the rest of the participants; we will peek at the original invite cached by the server to find out the identity of the original meeting creator
                # The original meeting creator will get a new scheduled message with an updated list of participant each time a new participant accepts the invite after the original scheduled message was sent.


                
                acceptedParticipants = self.conn.cursor().execute(
                    '''
                    SELECT * FROM inviteList where meetingNumber=? and status=?
                    ''',(acceptOrReject.meetingNumber, "Accepted")
                ).fetchall()
                
                confirm = model.Confirm(originalInvite.meetingNumber, len(seek)+1)

                if (freeSlot==True and totalAcceptedSoFar == minThreshold):
                    print("DB - 1")
                    self.conn.cursor().execute(
                        '''
                        INSERT INTO booked(date, time, meetingId, status, room) VALUES (?, ?, ?, ?, ?)
                        ''',(originalInvite.date, originalInvite.time, originalInvite.meetingNumber, "booked", len(seek)+1)
                    )

                message = model.encode(confirm)
                print("loc-0")
                listConfirmedParticipant = []
                for participant in acceptedParticipants:
                    pIp = participant[1]
                    pName = participant[2]
                    listConfirmedParticipant.append([pIp,pName])
                    if (pIp != requesterIP or pName != requesterPort):
                        if (freeSlot==True and totalAcceptedSoFar == minThreshold):
                            try:
                                print("Confirm-0")
                                self.s.sendto(message.encode(), (pIp, int(pName)))
                            except Exception as e:
                                print(e)
                                pass
                
                # If we find out the number of accepted participants can no longer meet the min participant threshold or no room is available, we'll send a cancel request to every participant regardless of accept or refused status
                if (howManyCanStillAccept == (minThreshold -1) or freeSlot == False):
                    allParticipants = self.conn.cursor().execute(
                        '''
                        SELECT * FROM inviteList where meetingNumber=?
                        ''',(acceptOrReject.meetingNumber,)
                    ).fetchall()

                    cancel = model.Cancel(originalInvite.meetingNumber, "Below Minimum Participant")
                    if (freeSlot == False):
                        cancel = model.Cancel(originalInvite.meetingNumber, "The room is no longer available due to another request confirming the room before you")
                    message = model.encode(cancel)
                    for participant in allParticipants:
                        pIp = participant[1]
                        pName = participant[2]
                        if (pIp != requesterIP or pName != requesterPort):
                            try:
                                print("Cancel-0")
                                self.s.sendto(message.encode(), (pIp, int(pName)))
                            except Exception as e:
                                print(e)
                                pass
                
                # Creating and sending message to requester. 
                print("loc-1")
                oldRequest = self.conn.cursor().execute(
                    '''
                    SELECT * FROM request where meetingNumber=?
                    ''', (originalInvite.meetingNumber,)
                ).fetchall()
                requestNumber = oldRequest[0][5]
                message = ''
                if (totalAcceptedSoFar >= minThreshold and freeSlot == True):
                    scheduled = model.Scheduled(requestNumber, originalInvite.meetingNumber, len(seek)+1, listConfirmedParticipant) # Testing
                    message = model.encode(scheduled)
                    try:
                        print("Schedule-2")
                        self.s.sendto(message.encode(), (requesterIP, int(requesterPort)))
                    except Exception as e:
                        print(e)
                        pass
                if (howManyCanStillAccept < minThreshold or freeSlot == False):
                    non_schedule = model.Non_Scheduled(requestNumber, originalInvite.meetingNumber, originalInvite.date, originalInvite.time, minThreshold, listConfirmedParticipant, originalInvite.topic)
                    message = model.encode(non_schedule)
                    try:
                        print("Non_Schedule-1")
                        self.s.sendto(message.encode(), (requesterIP, int(requesterPort)))
                    except Exception as e:
                        print(e)
                        pass
                print("loc-2")
                # If we already reached the min participant threshold before, we will only send a confirmation in response to the current sender instead of a batch message to all participants
                if (freeSlot==True and totalAcceptedSoFar > minThreshold):
                    if (requesterIP != addr[0] or requesterPort !=acceptOrReject.clientName):
                        try:
                            print("confirm-1")
                            self.s.sendto(message.encode(), (addr[0], int(acceptOrReject.clientName)))
                        except Exception as e:
                            print(e)
                            pass

                # Edge case handler-> meeting cancels, but sender did not receive the first cancelled response
                if (requesterIP != addr[0] or requesterPort !=acceptOrReject.clientName):
                    if (howManyCanStillAccept < minThreshold -1):
                        cancel = model.Cancel(originalInvite.meetingNumber, "Below Minimum Participant")
                        message = model.encode(cancel)
                        try:
                            print("cancel-1")
                            self.s.sendto(message.encode(), (addr[0], int(acceptOrReject.clientName)))
                        except Exception as e:
                            print(e)
                            pass

                self.lock.release()

        
        #self.s.sendto(("testss").encode(), (addr[0], 8000))



Server(1)