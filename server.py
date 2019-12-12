import socket
import sys
import model
import json
import threading
import collections
import sqlite3
import util
import time
import logging

HOST = ''
PORT = 8888

class Server:

    def __init__(self, numberOfMeetingRoom):
        self.meetingRoomNum = numberOfMeetingRoom
        self.lock = threading.Lock()
        self.ip = util.get_ip()
        self.conn = sqlite3.connect("Server.db", check_same_thread=False)

        logging.basicConfig(filename="server_log.txt",
                            filemode='a',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.DEBUG)

        #util.reset(self.conn)
        util.createServerBookingTable(self.conn)
        util.createServerRecevedRequestTable(self.conn)
        util.createServerInviteTable(self.conn)
        util.createServerInviteListTable(self.conn)
        util.createServerMeetingNumCacheTable(self.conn)
        util.createServerMeetingNumberToRoom(self.conn)
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
            HOST = self.ip
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
        #self.messageAckWatchdog()
        print("Server is running")


    def startMenu(self):
        print("*****Server IP")
        print(self.ip)
        threading.Thread(target=self._menu, args=(0,0,)).start()

    def messageAckWatchdog(self):
        threading.Thread(target=self.resendMessage).start()

    def resendMessage(self):
        while (self.running):
            notAckList = self.conn.cursor().execute(
            '''
            SELECT * FROM inviteList where status!='Sent'
            '''
            ).fetchall()

            time.sleep(50)
            print("Resending data")
            for sentInvite in notAckList:
                meetingNumber = sentInvite[0]
                ip = sentInvite[1]
                port = sentInvite[2]
                message = sentInvite[4]
                ackCheck = self.conn.cursor().execute(
                '''
                SELECT * FROM inviteList where meetingNumber=? and ip =? and client =? and status="Sent"
                ''', (meetingNumber, ip, port)
                ).fetchall()

                if (len(ackCheck) !=0):
                    self._sender(message, ip, port)

    def _menu(self, state, prevState, storedData =  {}):
        if (state == 0):
            print("\t****Server Main Menu*****")
            print("\t '1' for room change")
            print("\t'Exit' to turn off server")

            msg = input("\tEnter input: ")


            if (msg == "Exit"):
                self.running = False
                return
            if (msg.isdigit() and int(msg) == 1):
                seek = self.conn.cursor().execute(
                '''
                SELECT* from booked where status !="Cancelled"
                '''
                ).fetchall()
                print("****Room change menu")
                count = 0
                for row in seek:
                    print("[" + str(count) + "] " + str(row))
                    count+=1
                msg = input("Select a meeting: ")
                if (msg == "Q"):
                    return self._menu(0, 0)
                elif (msg.isdigit() and int(msg) >= 0 and int(msg) < len(seek)):
                    storedData["meeting"] = seek[int(msg)]
                    return self._menu(1, state, storedData)
                else:
                    print("\t****Invalid Command. Please try again")
                    return self._menu(state, prevState)
            else:
                print("\t****Invalid Command. Please try again")
                return self._menu(state, prevState)

        if (state == 1):
            msg = input("Select the new room number: ")
            if (msg == "Q"):
                    return self._menu(0, 0)
            elif (msg.isdigit() and int(msg) >= 0):
                selectedMeeting = storedData["meeting"]
                #print(storedData["meeting"])
                #print(selectedMeeting)
                meetingNumber = selectedMeeting[2]
                newRoomNumber = msg
                roomChange = model.Room_Change(meetingNumber, msg)

                message = model.encode(roomChange)
                inviteList = self.conn.cursor().execute(
                    '''
                        SELECT * from inviteList where meetingNumber=?
                    ''', (int(meetingNumber),)
                ).fetchall()

                for invite in inviteList:
                    ip = invite[1]
                    port = invite[2]

                    self._sender(message, ip, int(port))
                self.conn.cursor().execute(
                    '''
                    UPDATE booked SET room=? where meetingId=?
                    ''', (newRoomNumber, meetingNumber)
                )


                return self._menu(0, 0)
            else:
                print("\t****Invalid Command. Please try again")
                return self._menu(state, prevState, storedData)


    def startListner(self):
        threading.Thread(target=self._listener).start()

    def _sender(self, message, ip, port):
        try :
            logging.info("\nSending:" + str(message) + " to " + str((ip, port)))
            self.s.sendto(message.encode(), (ip, port))
            
        except Exception as e:
            print(e)
            sys.exit()

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
            logging.info("\nReceived:" + str(data, 'utf-8') + " from " + str(addr))
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
            #print("R-1")
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
                    #print("Message deja vu")
                    response = seek[0][1]
                    self._sender(response, addr[0], int(request.requestClientName))
                    #self.s.sendto(response.encode(), (addr[0], int(request.requestClientName)))
                else:
                    #print("Invalid message")
                    response = model.Response(request.requestNumber, request.requestClientName, "The request number has been previously used for another message")
                    response = model.encode(response)
                    self._sender(response, addr[0], int(request.requestClientName))
                    #self.s.sendto(response.encode(), (addr[0], int(request.requestClientName)))
                self.lock.release()
                return
            #print("R-2")
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
            #print("R-3")
            if (len(seek) > self.meetingRoomNum):
                #print("R-4")
                response = model.Response(request.requestNumber, request.requestClientName, "No room available")
                message = model.encode(response)
                try:
                    self._sender(message, addr[0], int(request.requestClientName))
                    #self.s.sendto(message.encode(), (addr[0], int(request.requestClientName)))
                except Exception as e:
                    print(e)
                    pass
            else:
                #print("R-5")
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
                print("WTF")
                print(request.participant)
                for participant in request.participant:
                    print("R-5-1")
                    invite.targetName = participant[1]
                    message = model.encode(invite)
                    try:
                        #print(participant[0])
                        #print(int(invite.targetName))
                        self._sender(message, participant[0], int(invite.targetName))
                        #self.s.sendto(message.encode(), (participant[0], int(invite.targetName)))
                    except Exception as e:
                        print(e)
                        pass
                    try:
                        self.conn.cursor().execute(
                            '''
                            INSERT INTO inviteList(meetingNumber, ip, client, status, message) VALUES (?, ?, ?, ?, ?)
                            ''', (invite.meetingNumber, participant[0], participant[1], "Sent", message)
                        )
                    except Exception as e:
                        print(e)
                        pass

            #print("R-6")
            self.conn.cursor().execute(
                '''
                INSERT INTO request(request, prevResponse, IP, client, requestNumber, meetingNumber) VALUES (?, ?, ?, ?, ?, ?)
                ''', (data, message, addr[0], request.requestClientName, request.requestNumber, meetingNumber)
            )
            util.commit(self.conn)
            self.lock.release()

        ###################################
        # Accept or Reject or Add handler 
        ###################################
        if (dataDict["type"] == "Accept" or dataDict["type"] == "Reject" or dataDict["type"] == "Add"):
            # Note that a client will continuously ping the server (send its accept meeting or reject meeting message every 5 seconds) until it receves either a cancel, confirm, scheduled or not_scheduled message from the server

            acceptOrReject = model.decodeJson(data)
            
            # Does the referenced meeting exists?
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
                self._sender(response, addr[0], int(acceptOrReject.clientName))
                #self.s.sendto(response.encode(), (addr[0], int(acceptOrReject.clientName)))
                self.lock.release()
                return

            if (len(invite) > 0):
                originalInvite = model.decodeJson(invite[0][1])
                requesterIP = originalInvite.requesterIP
                requesterPort = originalInvite.requesterName
                
                # Was this message sent by someone invited to the referenced meeting? 
                inviteList = self.conn.cursor().execute(
                    '''
                        SELECT * from inviteList where meetingNumber=? and ip=? and client=?
                    ''', (acceptOrReject.meetingNumber, addr[0], acceptOrReject.clientName)
                ).fetchall()
                # If the client is not invited to the meeting, was this an add request? 
                if (len(inviteList) == 0):
                    # If yes, we'll add it to the IP inviteList if the add request came from a new participant
                    if (dataDict["type"] == "Add"):
                        self.conn.cursor().execute(
                            '''
                                INSERT INTO inviteList(meetingNumber, ip, client, status) VALUES (?, ?, ?, ?)
                            ''', (acceptOrReject.meetingNumber, addr[0], acceptOrReject.clientName, "Added")
                        )
                        # Refresh the invite list
                        inviteList = self.conn.cursor().execute(
                            '''
                                SELECT * from inviteList where meetingNumber=? and ip=? and client=?
                            ''', (acceptOrReject.meetingNumber, addr[0], acceptOrReject.clientName)
                        ).fetchall()
                    else:
                        # If no we'll send a cancel message to avoid getting continuously pinged by the client instead of ignoring it
                        print("Participant was not invited")
                        message = model.Cancel(acceptOrReject.meetingNumber, "You are not invited to this meeting")
                        response = model.encode(message)
                        self._sender(response, addr[0], int(acceptOrReject.clientName))
                        #self.s.sendto(response.encode(), (addr[0], int(acceptOrReject.clientName)))
                        self.lock.release()
                        return

                if (dataDict["type"] == "Add"):
                    # If add request, we'll notify the original requester
                    added = model.Added(acceptOrReject.meetingNumber, addr[0], acceptOrReject.clientName)
                    message = model.encode(added)
                    self._sender(message, requesterIP, int(requesterPort))
                    #self.s.sendto(message.encode(), (requesterIP, int(requesterPort)))
                    # From now on, the "add" request will be treated as a "accept request" with the same logic
                    acceptOrReject = model.Accept(acceptOrReject.meetingNumber, acceptOrReject.clientName)


                # Update the tally of accepted and refused participants
                # if (inviteList[0][3] == "Sent"):
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

                # What's the total number of invitees for this meeting?
                totalInvites = self.conn.cursor().execute(
                    '''
                    SELECT COUNT(*) from inviteList where meetingNumber=? 
                    ''',(acceptOrReject.meetingNumber,)
                ).fetchone()[0]


                # How many accepted so far?
                totalAcceptedSoFar = self.conn.cursor().execute(
                    '''
                    SELECT COUNT(*) from inviteList where meetingNumber=? and status='Accepted'
                    ''',(acceptOrReject.meetingNumber,)
                ).fetchone()[0]

                # How many refused or withdrawn so far?
                totalRefusedSoFar = self.conn.cursor().execute(
                    '''
                    SELECT COUNT(*) from inviteList where meetingNumber=? and (status='Refused' or status='Withdrawn')
                    ''',(acceptOrReject.meetingNumber,)
                ).fetchone()[0]

                # Based on the current accepted or refused tally, can the meeting still happen?

                minThreshold = invite[0][2]
        
                howManyCanStillAccept = totalInvites - totalRefusedSoFar

                # If insufficient responses to come to a conclusion, we stop here and wait for more responses and do nothing for now and none of the code below will execute
                '''
                if (totalAcceptedSoFar < minThreshold and howManyCanStillAccept >= minThreshold):
                    self.lock.release()
                    return
                '''

                # Note that since the scheduler works on a first come first served basis, while it guarantees a room was free at the time the request was made, by the time the meeting gets confirmed, another request might have taken the room
                # If that happens, we will send a cancel message instead
                freeSlot = True
                addMeeting = True
                ##################
                try:
                    seek = self.conn.cursor().execute(
                    '''
                    SELECT * from booked where date=? and time=? and status !="Cancelled"
                    ''', (originalInvite.date, originalInvite.time)
                    ).fetchall()

                    '''
                    seek = self.conn.cursor().execute(
                    '''
                    #SELECT * from booked where date=? and time=? and meetingId!=? and status!='Cancelled'
                    ''', (originalInvite.date, originalInvite.time, originalInvite.meetingNumber)
                    ).fetchall()
                    '''
                    #print(originalInvite.meetingNumber)
                    #print(len(seek))
                except Exception as e:
                    print("Something went wrong")
                    print(e)
                    pass
                # If the meeting has already been scheduled, do not add a new entry. 
                if (len(seek) >= self.meetingRoomNum):
                    meetingNumber = seek[0][2]
                    #print("*!*!*!*!**!*!*!*!!*")
                    seek = self.conn.cursor().execute(
                        '''
                        SELECT * from booked where meetingId=?
                        ''', (originalInvite.meetingNumber,)
                        ).fetchall()
                    #print(len(seek))
                    if (len(seek) == 0):
                        freeSlot = False
                    else:
                        addMeeting = False
                ###############


                # If we have reached the min participant threshold for the first time, we will batch send messages to all those who have previously accepted the invite. Otherwise, a message will be sent only to the current correspondant
                # The original meeting creator will get a slightly different conformation than the rest of the participants; we will peek at the original invite cached by the server to find out the identity of the original meeting creator
                # The original meeting creator will get a new scheduled message with an updated list of participant each time a new participant accepts the invite after the original scheduled message was sent.
                
                acceptedParticipants = self.conn.cursor().execute(
                    '''
                    SELECT * FROM inviteList where meetingNumber=? and status=?
                    ''',(acceptOrReject.meetingNumber, "Accepted")
                ).fetchall()
                
                confirm = model.Confirm(originalInvite.meetingNumber, len(seek)+1)

                if (freeSlot==True and totalAcceptedSoFar == minThreshold):
                    #print("DB - 1")
                    if addMeeting:
                        try:
                            self.conn.cursor().execute(
                                '''
                                INSERT INTO booked(date, time, meetingId, status, room) VALUES (?, ?, ?, ?, ?)
                                ''',(originalInvite.date, originalInvite.time, originalInvite.meetingNumber, "booked", len(seek)+1)
                            )
                        except Exception as e:
                            print("Error Ocurred*****")
                            print(e)
                            pass

                        try:
                            self.conn.cursor().execute(
                                '''
                                INSERT INTO meetingToRoom(meetingNumber, room) VALUES (?, ?)
                                ''',(originalInvite.meetingNumber, len(seek)+1)
                            )
                        except Exception as e:
                            print("Error Ocurred*****")
                            print(e)
                            pass

                message = model.encode(confirm)
                #print("loc-0")
                seekMeetingRoom = self.conn.cursor().execute(
                    '''
                    SELECT * from meetingToRoom where meetingNumber=?
                    ''',(originalInvite.meetingNumber, )
                ).fetchall()
                meetingRoom = -1
                if (len(seekMeetingRoom)> 0):
                    meetingRoom = seekMeetingRoom[0][1]

                listConfirmedParticipant = []
                for participant in acceptedParticipants:
                    pIp = participant[1]
                    pName = participant[2]
                    listConfirmedParticipant.append([pIp,pName])
                    if (pIp != requesterIP or pName != requesterPort):
                        if (freeSlot==True and totalAcceptedSoFar == minThreshold):
                            try:
                                print("Confirm-0")
                                self._sender(message, pIp, int(pName))
                                #self.s.sendto(message.encode(), (pIp, int(pName)))
                            except Exception as e:
                                print(e)
                                pass
                
                # If we find out the number of accepted participants can no longer meet the min participant threshold or no room is available, we'll send a cancel request to every participant regardless of accept or refused status
                if (howManyCanStillAccept == (minThreshold -1) or freeSlot == False):
                    allParticipants = self.conn.cursor().execute(
                        '''
                        SELECT * FROM inviteList where meetingNumber=? and status!='withdrawn'
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
                                #print("Cancel-0")
                                self._sender(message, pIp, int(pName))
                                #self.s.sendto(message.encode(), (pIp, int(pName)))
                            except Exception as e:
                                print(e)
                                pass
                
                # Creating and sending message to requester. 
                #print("loc-1")
                oldRequest = self.conn.cursor().execute(
                    '''
                    SELECT * FROM request where meetingNumber=?
                    ''', (originalInvite.meetingNumber,)
                ).fetchall()
                requestNumber = oldRequest[0][5]
                message = ''
                if (totalAcceptedSoFar >= minThreshold and freeSlot == True):
                    scheduled = model.Scheduled(requestNumber, originalInvite.meetingNumber, meetingRoom, listConfirmedParticipant) # Testing
                    message = model.encode(scheduled)
                    try:
                        #print("Schedule-2")
                        self._sender(message, requesterIP, int(requesterPort))
                        #self.s.sendto(message.encode(), (requesterIP, int(requesterPort)))
                    except Exception as e:
                        print(e)
                        pass
                if (howManyCanStillAccept < minThreshold or freeSlot == False):
                    non_schedule = model.Non_Scheduled(requestNumber, originalInvite.meetingNumber, originalInvite.date, originalInvite.time, minThreshold, listConfirmedParticipant, originalInvite.topic)
                    message = model.encode(non_schedule)
                    try:
                        #print("Non_Schedule-1")
                        self._sender(message, requesterIP, int(requesterPort))
                        #self.s.sendto(message.encode(), (requesterIP, int(requesterPort)))
                    except Exception as e:
                        print(e)
                        pass
                #print("loc-2")
                # If we already reached the min participant threshold before and a new participant accept the meeting, we will only send a confirmation in response to the current sender instead of a batch message to all participants
                # The requester should had received a new participant list including this new participant with the above code
                # Edge case handler-> sender did not receive the first confirm response. We'll resend the message here. 
                if (freeSlot==True and totalAcceptedSoFar > minThreshold):
                    if (requesterIP != addr[0] or requesterPort !=acceptOrReject.clientName):
                        try:
                            #print("confirm-1")
                            confirm = model.Confirm(originalInvite.meetingNumber, meetingRoom)
                            message = model.encode(confirm)
                            self._sender(message, addr[0], int(acceptOrReject.clientName))
                            #self.s.sendto(message.encode(), (addr[0], int(acceptOrReject.clientName)))
                        except Exception as e:
                            print(e)
                            pass

                # Edge case handler-> meeting cancelled, but sender did not receive the first cancelled response. We'll resend the message
                if (requesterIP != addr[0] or requesterPort !=acceptOrReject.clientName):
                    if (howManyCanStillAccept < minThreshold -1):
                        cancel = model.Cancel(originalInvite.meetingNumber, "Below Minimum Participant")
                        message = model.encode(cancel)
                        try:
                            #print("cancel-1")
                            self._sender(message, addr[0], int(acceptOrReject.clientName))
                            #self.s.sendto(message.encode(), (addr[0], int(acceptOrReject.clientName)))
                        except Exception as e:
                            print(e)
                            pass

                self.lock.release()

        if (dataDict["type"] == "Withdraw"):
            withdraw = model.decodeJson(data)

            # Does the referenced meeting exists?
            self.lock.acquire()
            seek = self.conn.cursor().execute(
                '''
                    SELECT * from booked where meetingId=?
                ''', (withdraw.meetingNumber, )
            ).fetchall()
            if (len(seek) > 0):
                # Was the person in the invite list?
                seek = self.conn.cursor().execute(
                '''
                    SELECT * from inviteList where meetingNumber=? and ip=? and client=?
                ''', (withdraw.meetingNumber, addr[0], int(withdraw.clientName))
                ).fetchall()
                
                if (len(seek) > 0):
                    # If yes, fetch the saved copy of the original invite to find out the ip and sessionName of the requester, the min threshold, etc.
                    seek = self.conn.cursor().execute(
                    '''
                        SELECT * from invite where meetingNumber=?
                    ''', (withdraw.meetingNumber, )
                    ).fetchall()
                    # And update the status of the invitee to withdrawn
                    self.conn.cursor().execute(
                    '''
                    UPDATE inviteList SET status=? where meetingNumber=? and ip=? and client=?
                    ''', ("Withdrawn", withdraw.meetingNumber, addr[0], withdraw.clientName)
                    )

                    if (len(seek)>0):
                        inviteStr = seek[0][1]
                        invite = model.decodeJson(inviteStr)

                        minParticipant = int(seek[0][2])

                        # check to see if below min now
                        # How many accepted now?
                        totalAcceptedSoFar = self.conn.cursor().execute(
                            '''
                            SELECT COUNT(*) from inviteList where meetingNumber=? and status='Accepted'
                            ''',(withdraw.meetingNumber,)
                        ).fetchone()[0]

                        # Based on the current accepted rate, can the meeting still happen after the withdrawal?
                

                        if (totalAcceptedSoFar < minParticipant):
                            # cancel the entire meeting; send notification to all participants
                            allParticipants = self.conn.cursor().execute(
                                '''
                                SELECT * FROM inviteList where meetingNumber=? and status!='Withdrawn'
                                ''',(withdraw.meetingNumber,)
                            ).fetchall()

                            self.conn.cursor().execute(
                            '''
                            UPDATE booked SET status="Cancelled" where meetingId=?
                            ''', (withdraw.meetingNumber,)
                            )

                            cancel = model.Cancel(withdraw.meetingNumber, "Below Minimum Participant due to withdrawal")
                            message = model.encode(cancel)
                            for participant in allParticipants:
                                pIp = participant[1]
                                pName = participant[2]
                                try:
                                    self._sender(message, pIp, int(pName))
                                    #self.s.sendto(message.encode(), (pIp, int(pName)))
                                except Exception as e:
                                    print(e)
                                    pass
                        else:
                            withdraw = model.Withdraw(withdraw.meetingNumber, withdraw.clientName, addr[0])
                            message = model.encode(withdraw)
                            requesterIP = invite.requesterIP
                            requesterPort = invite.targetName
                            try:
                                self._sender(message, requesterIP, int(requesterPort))
                                #self.s.sendto(message.encode(), (requesterIP, int(requesterPort)))
                            except Exception as e:
                                print(e)
                                pass
            self.lock.release()

        if (dataDict["type"] == "Cancel"):
            cancel = model.decodeJson(data)
            #print("Cancel-1")
            self.lock.acquire()

            # Does the referenced meeting exists?
            seek = self.conn.cursor().execute(
                '''
                    SELECT * from booked where meetingId=?
                ''', (cancel.meetingNumber, )
            ).fetchall()

            if (len(seek) > 0):
                #print("Cancel-2")
                # If yes, fetch the saved copy of the original invite to find out the ip and sessionName of the requester, the min threshold, etc.
                seek = self.conn.cursor().execute(
                '''
                    SELECT * from invite where meetingNumber=?
                ''', (cancel.meetingNumber, )
                ).fetchall()
                if (len(seek)>0):
                    #print("Cancel-3")
                    inviteStr = seek[0][1]
                    invite = model.decodeJson(inviteStr)
                    requesterIP = invite.requesterIP
                    requesterName = invite.requesterName
                    # If the current message indeed was sent by the original meeting requester, we cancel the meeting and send a message to all participants
                    if (requesterIP == addr[0] and requesterName == cancel.clientName):
                        #print("Cancel-4")
                        self.conn.cursor().execute(
                        '''
                        UPDATE booked SET status="Cancelled" where meetingId=?
                        ''', (cancel.meetingNumber,)
                        )

                        # cancel the entire meeting; send notification to all participants
                        allParticipants = self.conn.cursor().execute(
                            '''
                            SELECT * FROM inviteList where meetingNumber=? and status!='Withdrawn'
                            ''',(cancel.meetingNumber,)
                        ).fetchall()

                        cancel = model.Cancel(cancel.meetingNumber, "Cancelled by the organizer")
                        message = model.encode(cancel)
                        #print("Cancel-5")
                        for participant in allParticipants:
                            pIp = participant[1]
                            pName = participant[2]
                            try:
                                self._sender(message, pIp, int(pName))
                                #self.s.sendto(message.encode(), (pIp, int(pName)))
                            except Exception as e:
                                print(e)
                                pass

            self.lock.release()
        #self.s.sendto(("testss").encode(), (addr[0], 8000))



Server(2)