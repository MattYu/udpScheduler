import tkinter as tk
import util
from tkinter import ttk, messagebox
import model
root = tk.Tk()
root.title("UDP Scheduler")
nb = ttk.Notebook(root)

def set_nb(root):
    nb = ttk.Notebook(root)

class MainView(tk.Frame):

    client = None

    def __init__(self, *args, **kwargs):
        tk.Frame.__init__(self, root)

    def refreshUI(self):
        self.client.lock.acquire()
        self.confirmed_meetings_list = util.getConfirmedList(self.client.conn)
        self.confirmed_meetings['values'] = util.getConfirmedList(self.client.conn)
        self.requested_meetings_list = util.getScheduledList(self.client.conn)
        self.requested_meetings['values'] = util.getScheduledList(self.client.conn)
        self.agenda['values'] = util.getEntireList(self.client.conn)
        self.client.lock.release()

    def execute(self, client):
        self.client = client
        def populate_listbox():
            db_list = util.getParticipantList(self.client.conn)
            participant_list.delete(0, tk.END)
            for item in db_list:
                participant_list.insert(tk.END, item)
            
        def create_meeting():
            day = meeting_day.get()
            month = meeting_month.get()
            hour = meeting_hour.get()
            min_num_participants = min_participants.get()
            topic = meeting_topic.get()
            selected_participants = [[participant_list.get(i)[1], participant_list.get(i)[2]] for i in participant_list.curselection()]
            if (day == "" or month == "" or hour == "" or min_num_participants == "" or topic=="" or len(selected_participants) == 0):
                messagebox.showerror("create meeting", "Form cannot be empty")
            elif (not day.isdigit() or int(day) < 1 or int(day) > 31):
                messagebox.showerror("create meeting", "Invalid day entered")
            elif (not month.isdigit() or int(month) < 1 or int(month) > 12):
                messagebox.showerror("create meeting", "Invalid month entered")
            elif (not hour.isdigit() or int(hour) < 1 or int(hour) > 24):
                messagebox.showerror("create meeting", "Invalid hour entered")
            elif (not min_num_participants.isdigit() or int(min_num_participants) < 1):
                messagebox.showerror("create meeting", "Invalid participant number entered")
            else:
                self.client.lock.acquire()
                seek = self.client.conn.cursor().execute(
                    '''
                    SELECT * from booking where date like ? and time like ? and (status="Scheduled" or status="Confirmed")
                    ''', (month + "-" + day, hour)
                ).fetchall()
                self.client.lock.release()
                if (len(seek) > 0):
                    messagebox.showerror("create meeting", "You have another meeting at the same time. Please cancel or withdrawal your other meeting first")
                else:
                    selected_participants.append([self.client.ip, self.client.sessionName])
                    request = model.Request(month + "-" + day, hour,min_num_participants, selected_participants, topic, self.client.sessionName)
                    message = model.encode(request)

                    try:
                        self.client.conn.cursor().execute(
                            '''
                            INSERT INTO booking(date, time, meetingNumber, sourceIP, sourceClient, status, room, confirmedParticipant, topic, reason, min) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''',(month + "-" + day, hour, "unassigned", self.client.ip, self.client.sessionName, "sent", "no room yet", "", topic, "", "")
                        )
                        self.client.conn.cursor().execute(
                            '''
                            INSERT INTO requestNum(lastRequestNum) VALUES(?)
                            ''',(request.requestNumber,)
                        )
                    except Exception as e:
                        print(e)
                        pass
                    self.client._sender(message)

        def add_new_contact():
            ip = new_ip.get()
            name = new_name.get()
            if ip == "":
                messagebox.showerror("add contact", "NO IP ENTERED")
            elif name == "":
                messagebox.showerror("add contact", "NO NAME ENTERED")
            else:
                messagebox.showinfo("add contact", "ADDED %s - %s" % (str(ip), str(name)))
                util.addParticipant(self.client.conn, ip, name)
                populate_listbox()

        def withdraw_from_confirmed():
            meeting = confirmed_meetings.get()
            index = confirmed_meetings.current()

            if meeting != "":
                messagebox.showinfo("withdraw", "WITHDRAW FROM %s" % meeting)
                meetingNumber = self.confirmed_meetings_list[index][2]
                withdraw = model.Withdraw(meetingNumber, self.client.sessionName)
                message = model.encode(withdraw)
                messageType = "Withdrawn"
                self.client._sender(message)
                self.client.lock.acquire()
                self.client.conn.cursor().execute(
                    '''
                    UPDATE booking SET status=? where meetingNumber=?
                    ''',(messageType, meetingNumber)
                )
                confirmed_meetings.config(values=util.getConfirmedList(self.client.conn)) # TODO - update with right list
                self.client.lock.release()
                self.refreshUI()
            else:
                messagebox.showerror("withdraw", "NO MEETING SELECTED")

        def cancel_from_requested():
            meeting = requested_meetings.get()
            index = requested_meetings.current()
            if meeting != "":
                messagebox.showinfo("cancel", "CANCEL %s" % meeting)
                #onfirmed_meetings.config(values=util.getParticipantList(self.client.conn)) # TODO - update with right list
                meetingNumber = self.requested_meetings_list[index][2]
                print("debugging")
                print(meetingNumber)
                print(meeting)
                cancel = model.Cancel(meetingNumber, '', self.client.sessionName)
                message = model.encode(cancel)
                messageType = "Cancelled"
                self.client._sender(message)
                self.client.lock.acquire()
                self.client.conn.cursor().execute(
                    '''
                    UPDATE booking SET status=? where meetingNumber=?
                    ''',(messageType, meetingNumber)
                )
                requested_meetings.config(values=util.getScheduledList(self.client.conn)) 
                self.client.lock.release()
                self.refreshUI()     
            else:
                messagebox.showerror("cancel", "NO MEETING SELECTED")

        def view_from_agenda():
            meeting3 = agenda.get()
            if meeting3 != "":
                messagebox.showinfo("Meeting", "Meeting info %s" % meeting3)


        splash_tab = tk.Frame(nb)
        nb.add(splash_tab, text="Welcome")
        meeting_req_tab = tk.Frame(nb)
        nb.add(meeting_req_tab, text="Book Meeting")
        meetings_tab = tk.Frame(nb)
        nb.add(meetings_tab, text="Meeting Management")
        agenda_tab = tk.Frame(nb)
        nb.add(agenda_tab, text="Agenda")
        contacts_tab = tk.Frame(nb)
        nb.add(contacts_tab, text="Contacts")
        nb.pack()

        # Splash Page
        tk.Label(splash_tab, text="").pack()
        tk.Label(splash_tab, text="UDP SCHEDULER", font=('Helvetica', 24, 'bold')).pack()
        tk.Label(splash_tab, text="COEN 445", font="bold").pack()
        tk.Label(splash_tab, text="").pack()
        tk.Label(splash_tab, text="By:").pack()
        tk.Label(splash_tab, text="C. Kokorogiannis, T. Serrano, M.T. Yu").pack()
        tk.Label(splash_tab, text="").pack()
        tk.Label(splash_tab, text="").pack()
        tk.Label(splash_tab, text="IP: %s:%s" % (str(client.host), str(client.sessionName))).pack()

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
        confirmed_meetings = ttk.Combobox(meetings_tab, values=util.getConfirmedList(self.client.conn), height=5, width=70, state="readonly") # TODO - get right list
        confirmed_meetings.grid(row=1, column=1, pady=5, sticky="NW")
        self.confirmed_meetings = confirmed_meetings
        withdraw_confirmed = tk.Button(meetings_tab, text="Withdraw", command=lambda: withdraw_from_confirmed()).grid(row=2, column=1, sticky="E") # TODO - complete withdraw function
        tk.Label(meetings_tab, text="Requested Meetings:").grid(row=4, column=0, pady=5, padx=(5, 0), sticky="NW")
        requested_meetings = ttk.Combobox(meetings_tab, values=util.getScheduledList(self.client.conn), height=5, width=70, state="readonly") # TODO - get right list
        self.requested_meetings = requested_meetings
        requested_meetings.grid(row=4, column=1, pady=5, stick="NW")
        cancel_requested = tk.Button(meetings_tab, text="Cancel", command=lambda: cancel_from_requested()).grid(row=5, column=1, sticky="E") # TODO - complete cancel function

        # Contacts
        tk.Label(contacts_tab, text="Contacts", font="bold", justify="center").grid(row=0, column=2, pady=(10, 10), sticky="N")
        tk.Label(contacts_tab, text="Contacts:").grid(row=1, column=0, pady=5, padx=(5, 0), sticky="W")
        contacts = ttk.Combobox(contacts_tab, values=util.getParticipantList(self.client.conn), height=5, state="readonly")
        contacts.grid(row=1, column=1, pady=5, padx=(0, 5), sticky="W")
        ttk.Separator(contacts_tab, orient="horizontal").grid(row=2, columnspan=6, pady=10, padx=5, sticky="EW")
        tk.Label(contacts_tab, text="Add Contact:").grid(row=3, column=0, pady=(0, 10), padx=5, sticky="W")
        tk.Label(contacts_tab, text="Contact IP:").grid(row=4, column=0, padx=(5, 0), sticky="W")
        new_ip = tk.Entry(contacts_tab)
        new_ip.grid(row=4, column=1, sticky="W")
        tk.Label(contacts_tab, text="Contact Port:").grid(row=4, column=2, padx=5, sticky="W")
        new_name = tk.Entry(contacts_tab)
        new_name.grid(row=4, column=3, sticky="W")
        add_contact = tk.Button(contacts_tab, text="Add", fg="green", command=lambda: add_new_contact())
        add_contact.grid(row=4, column=4, sticky="E", padx=10)

        #Agenda
        tk.Label(agenda_tab, text="Agenda", font="bold", justify="center")\
            .grid(row=0, column=0, columnspan=6, pady=10, sticky="N")
        agenda = ttk.Combobox(agenda_tab, values=util.getEntireList(self.client.conn), height=5, width=100, state="readonly")
        agenda.grid(row=1,sticky="NW")
        self.agenda = agenda
        view_agenda = tk.Button(agenda_tab, text="View Agenda", command=lambda: view_from_agenda()).grid(row=2, column=0, sticky="E")


if __name__ == "__main__":
    main = MainView(root)
    main.pack(side="top", fill="both", expand=True)
    root.mainloop()