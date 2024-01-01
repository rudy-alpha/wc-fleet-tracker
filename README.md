# WC-Auth
Basic Fleet Tracking and ESI Viewing Flask Appliciation for Winter Coalition PAP backend.

Authentication handles all scopes through the login endpoint and this will be expanded into a redevelopment of an ESI viewing tool (Crobar Copy I am calling Carbon).
 - Request generating a report and fetch ESI on specific users.
 - Automatic Report generation on flagged users. (and flagging users!) eg. TEST Group Please Ignore, Probably Spy.
 - Hull ID mapping and other fancy automation tools.
 - Supercapital and Structure Tracking.

FleetTracking.py is the current Frontend which is being development into a simple to use webpage that can allow users to track their current fleet attendance, FCs to pap fleets, and overall CI viewing Fleet Attendance.

Fleet information includes: fc_name, pap_type, and fleet_members alongside their time in fleet, ships, and systems.

Eventually:
- Linking characters through Auth.
- Ingame Fleet/Mumble Concurrance (longside Mumble Hash archiving).
- Extra PAP for people doing special things eg. FC backseating.
- Frontend Discord Bot (CI Bot integration) / Webpage (with IP/user_agent logging).

Notice: Secret Keys, etc. used in this are test applications and obviously do not represent the productive environment.
