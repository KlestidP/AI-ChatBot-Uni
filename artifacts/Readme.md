**Artifacts for AI Chatbot Project**

**1\. What People Actually Need**

* **Common Questions** – Collected from students and Freshies group chats

  1) These are the questions most often asked by students, the general/vague prompts which will be used to train the chatbot. Here is a list of them

     1) Where do I receive my Immatrikulationsbeschenigung?

        2) How do I access my Semester Ticket \+ map of validity?

        3) Where is the \[college name, dorm letter\] laundry room located?

        4) How do I submit my request for a residence permit/address change/driving license conversion?

        5) When are the locker opening hours?

        6) List of emergency contacts (police/college services)

        7) Software accessible with a university account

        8) Servery hours/menu

        9) Class Location/Time

        10) \[Degree Name\] Semester Plan

        11) Exam Schedules

        12) What events are happening today/this week/etc.?

        13) Process to submit \[document\] request

        14) Medical care/Clinic or hospital location+phone numbers

        15) General IT guidelines (vpn, ethernet, wifi, teamwork, outlook, moodle, lms)

        16) \[Optional: virtual academic advisor\]

**2\. Dataset**

* **Dataset Collection** – All the queries and responses it should learn from

  1) This also includes all the available sources of information it can use to provide responses, which include:

     1) Study programs

        2) \[degree\] handbooks

        3) Government sites \[for residence permits, driving licenses\]

        4) CampusNet/Moodle/Learner

        5) Constructor University Website


**3\. Deployment Plan – Steps to put it online (Telegram, Domain)**

| Criteria | Telegram Bot | WhatsApp Bot | Standalone Website |
| :---- | :---- | :---- | :---- |
| **Cost** | Completely free | Limited free tier, but costs increase with usage | Free hosting options available (GitHub Pages, Vercel, Heroku) |
| **Hosting** | No external hosting needed | Requires backend hosting | Requires hosting for backend |
| **Integration** | Simple API (python-telegram-bot) | Requires WhatsApp Business API approval (time-consuming) | Full control over UI & chatbot logic |
| **Functionality** | Supports text, images, buttons | High student adoption but API restrictions | Fully customizable and accessible from any browser |
| **User Adoption** | Requires Telegram (not all students use it) | Most students already use WhatsApp | No app required, works for everyone |
| **Development Effort** | Minimal (ready-to-use API) | Medium (requires API setup and approval) | High (front-end \+ back-end needed) |

**We will be creating a telegram Bot with telegram API** or python-telegram bot.



**Future Development:**

**1\. How Users Will Talk to the Chatbot (this will be done on later stages)**

* **Example Chats** – Sample conversations to map out responses

* **UI Sketches** – Basic wireframes of how it’ll look

* **Chat Flow Diagram** – Visualizing how the chatbot should respond

**2\. How Users Will Talk to the Chatbot (this will be done on later stages)**

* **Example Chats** – Sample conversations to map out responses

* **UI Sketches** – Basic wireframes of how it’ll look

* **Chat Flow Diagram** – Visualizing how the chatbot should respond

**3\. Training & Building the Chatbot**

* **NLP Model Plan** – Which model we’re using and how we train it

* **Performance Report** – How well the chatbot understands stuff (accuracy, errors, etc.)

**4\. Making It Work with Other Systems**

* **Architecture Diagram** – How everything connects (chatbot, database, website, etc.)

* **Database Schema** – Structure of stored queries & responses

* **API Docs** – How the chatbot connects to the site/app

**5\. Testing & Going Live (The last step in the process)**

* **Test Scenarios** – What to test to make sure it works properly
