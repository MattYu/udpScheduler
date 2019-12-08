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
from tkinter import ttk, messagebox

# REPLACE THIS WITH SERVER'S IP (Server IP printed when first executing 'python3 server.py')
host = '10.32.10.6'
#host = 'localhost'
port = 8888

root = tk.Tk()
root.title("UDP Scheduler")
nb = ttk.Notebook(root)

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

        def populate_listbox():
            db_list = util.getParticipantList(self.conn)
            participant_list.delete(0, tk.END)
            for item in db_list:
                participant_list.insert(tk.END, item)

        # TODO - Add meeting to DB
        def create_meeting():
            day = meeting_day.get()
            month = meeting_month.get()
            hour = meeting_hour.get()
            min_num_participants = min_participants.get()
            topic = meeting_topic.get()
            selected_participants = [participant_list.get(i) for i in participant_list.curselection()]

        # TODO - Add new contact
        def add_new_contact():
            ip = new_ip.get()
            name = new_name.get()
            if ip == "":
                messagebox.showerror("add contact", "NO IP ENTERED")
            elif name == "":
                messagebox.showerror("add contact", "NO NAME ENTERED")
            else:
                messagebox.showinfo("add contact", "PLACEHOLDER FUNCTION NOT DONE - ADDED %s - %s" % (str(ip), str(name)))
                # Add contact to participant listbox
                populate_listbox()

        def withdraw_from_confirmed():
            meeting = confirmed_meetings.get()
            if meeting != "":
                messagebox.showinfo("withdraw", "PLACEHOLDER - WITHDRAW FROM %s" % meeting)
                confirmed_meetings.config(values=util.getParticipantList(self.conn)) # TODO - update with right list
            else:
                messagebox.showerror("withdraw", "NO MEETING SELECTED")

        def cancel_from_requested():
            meeting = requested_meetings.get()
            if meeting != "":
                messagebox.showinfo("cancel", "PLACEHOLDER - CANCEL %s" % meeting)
                confirmed_meetings.config(values=util.getParticipantList(self.conn)) # TODO - update with right list
            else:
                messagebox.showerror("cancel", "NO MEETING SELECTED")

        splash_tab = tk.Frame(nb)
        nb.add(splash_tab, text="Welcome")
        meeting_req_tab = tk.Frame(nb)
        nb.add(meeting_req_tab, text="Book Meeting")
        meetings_tab = tk.Frame(nb)
        nb.add(meetings_tab, text="Meeting Management")
        contacts_tab = tk.Frame(nb)
        nb.add(contacts_tab, text="Contacts")
        nb.pack()

        # Splash Page
        tk.Label(splash_tab, text="").pack()
        tk.Label(splash_tab, text="UDP SCHEDULER", font=('Helvetica', 24, 'bold')).pack()
        tk.Label(splash_tab, text="COEN 445", font="bold").pack()
        tk.Label(splash_tab, text="").pack()
        tk.Label(splash_tab, text="By:").pack()
        tk.Label(splash_tab, text="C. Kokorogiannis, T. Serrano, M. Tao Yu").pack()
        tk.Label(splash_tab, text="").pack()
        tk.Label(splash_tab, text="").pack()
        tk.Label(splash_tab, text="IP: %s:%s" % (str(host), str(port))).pack()

        # Book a meeting
        tk.Label(meeting_req_tab, text="Book a Meeting", font="bold", justify="center")\
            .grid(row=0, column=0, columnspan=6, pady=10, sticky="N")
        tk.Label(meeting_req_tab, text="Month:").grid(row=1, column=0, pady=5, padx=(5, 0), sticky="W")
        meeting_month = tk.Entry(meeting_req_tab)
        meeting_month.grid(row=1, column=1, pady=5, padx=(0, 5), sticky="W")
        tk.Label(meeting_req_tab, text="Day:").grid(row=1, column=2, pady=5, padx=(5, 0), sticky="W")
        meeting_day = tk.Entry(meeting_req_tab)
        meeting_day.grid(row=1, column=3, pady=5, padx=(0, 5), sticky="W")
        tk.Label(meeting_req_tab, text="Hour:").grid(row=1, column=4, pady=5, padx=(5, 0), sticky="W")
        meeting_hour = tk.Entry(meeting_req_tab)
        meeting_hour.grid(row=1, column=5, pady=5, padx=(5, 5), sticky="W")
        tk.Label(meeting_req_tab, text="Minimum Participants:").grid(row=2, column=0, pady=5, padx=(5, 0), sticky="W")
        min_participants = tk.Entry(meeting_req_tab)
        min_participants.grid(row=2, column=1, pady=5, padx=(0, 5), sticky="W")
        tk.Label(meeting_req_tab, text="Meeting Topic:").grid(row=2, column=2, pady=5, padx=(5, 0), sticky="W")
        meeting_topic = tk.Entry(meeting_req_tab)
        meeting_topic.grid(row=2, column=3, pady=5, padx=(0, 5), sticky="W")
        tk.Label(meeting_req_tab, text="Select Participants:").grid(row=3, column=0, pady=5, padx=(5, 0), sticky="W")
        participant_list = tk.Listbox(meeting_req_tab, selectmode='multiple', height=5)
        participant_list.grid(row=3, column=1, pady=5, padx=(0, 5), sticky="W")
        submit_meeting_req = tk.Button(meeting_req_tab, text="Submit", fg="green", command=lambda: create_meeting())
        submit_meeting_req.grid(row=3, column=5, pady=(0, 10), padx=10, sticky="SE")
        populate_listbox()

        # Meeting Management
        tk.Label(meetings_tab, text="Meeting Management", font="bold", justify="center") \
            .grid(row=0, column=0, columnspan=6, pady=(10, 30), sticky="N")
        tk.Label(meetings_tab, text="Confirmed Meetings:").grid(row=1, column=0, pady=(5, 0), padx=(5, 0), sticky="NW")
        confirmed_meetings = ttk.Combobox(meetings_tab, values=util.getParticipantList(self.conn), height=5, state="readonly") # TODO - get right list
        confirmed_meetings.grid(row=1, column=1, pady=5, sticky="NW")
        withdraw_confirmed = tk.Button(meetings_tab, text="Withdraw", command=lambda: withdraw_from_confirmed()).grid(row=2, column=1, sticky="E") # TODO - complete withdraw function
        tk.Label(meetings_tab, text="Requested Meetings:").grid(row=1, column=2, pady=5, padx=(100, 0), sticky="NW")
        requested_meetings = ttk.Combobox(meetings_tab, values=util.getParticipantList(self.conn), height=5, state="readonly") # TODO - get right list
        requested_meetings.grid(row=1, column=3, pady=5, stick="NW")
        cancel_requested = tk.Button(meetings_tab, text="Cancel", command=lambda: cancel_from_requested()).grid(row=2, column=3, sticky="E") # TODO - complete cancel function

        # Contacts
        tk.Label(contacts_tab, text="Contacts", font="bold", justify="center").grid(row=0, column=2, pady=(10, 10), sticky="N")
        tk.Label(contacts_tab, text="Contacts:").grid(row=1, column=0, pady=5, padx=(5, 0), sticky="W")
        contacts = ttk.Combobox(contacts_tab, values=util.getParticipantList(self.conn), height=5, state="readonly")
        contacts.grid(row=1, column=1, pady=5, padx=(0, 5), sticky="W")
        ttk.Separator(contacts_tab, orient="horizontal").grid(row=2, columnspan=6, pady=10, padx=5, sticky="EW")
        tk.Label(contacts_tab, text="Add Contact:").grid(row=3, column=0, pady=(0, 10), padx=5, sticky="W")
        tk.Label(contacts_tab, text="Contact IP:").grid(row=4, column=0, padx=(5, 0), sticky="W")
        new_ip = tk.Entry(contacts_tab)
        new_ip.grid(row=4, column=1, sticky="W")
        tk.Label(contacts_tab, text="Contact Name:").grid(row=4, column=2, padx=5, sticky="W")
        new_name = tk.Entry(contacts_tab)
        new_name.grid(row=4, column=3, sticky="W")
        add_contact = tk.Button(contacts_tab, text="Add", fg="green", command=lambda: add_new_contact())
        add_contact.grid(row=4, column=4, sticky="E", padx=10)


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
                SELECT * from booking where date like ? and time like ? and (status="Scheduled" or status="Confirmed")
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
                print(count)
                print(row)
                count+=1

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
                count += 1

            msg = input("Enter a meeting number:")
            if (msg == "Q"):
                return self._menu(0, 0)
            elif (msg.isdigit() and int(msg) >= 0 and int(msg) < len(seek)):
                meetingNumber = seek[int(msg)][2]
                cancel = model.Cancel(meetingNumber, '', self.sessionName)
                storedData["message"] = model.encode(cancel)
                storedData["type"] = "Cancelled"
                storedData["meetingNumber"] = meetingNumber
                return self._menu(13, state, storedData)
            else:
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState)

        if (state == 13):
            print("****Are you sure?")
            msg = input("Y/N:")
            if (msg == "Y"):
                self._sender(storedData["message"])
                self.conn.cursor().execute(
                    '''
                    UPDATE booking SET status=? where meetingNumber=?
                    ''',(storedData["type"] , storedData["meetingNumber"])
                )
                print("Sent")
                return self._menu(0, 0)
            if (msg == "N"):
                return self._menu(prevState, state, storedData)
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
                count +=1

            msg = input("Enter a meeting number:")
            if (msg == "Q"):
                return self._menu(0, 0)
            elif (msg.isdigit() and int(msg) >= 0 and int(msg) < len(seek)):
                meetingNumber = seek[int(msg)][2]
                withdraw = model.Withdraw(meetingNumber, self.sessionName)
                storedData["message"] = model.encode(withdraw)
                storedData["type"] = "Withdrawn"
                storedData["meetingNumber"] = meetingNumber
                return self._menu(13, state, storedData)
            else:
                print("****Invalid Command. Please try again")
                return self._menu(state, prevState)

        root.mainloop()



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
                SELECT * from booking where date=? and time=? and status !="Cancelled" and status !="Non Scheduled" and status!="Withdrawn"
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
                    print("*************************!!!!!!!!!!!!!!!*****************************")
                    for row in seek:
                        print(row)
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
                        UPDATE booking SET status=? where meetingNumber=? and status!="Cancelled"
                        ''', (status, meetingStatus.meetingNumber)
                    )

                    self.conn.cursor().execute(
                        '''
                        UPDATE booking SET reason=? where meetingNumber=? and status!="Cancelled"
                        ''', (reason, meetingStatus.meetingNumber)
                    )

                    self.conn.cursor().execute(
                        '''
                        UPDATE booking SET room=? where meetingNumber=? and status!="Cancelled"
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