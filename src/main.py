# coding=utf-8
from flask import Flask, jsonify, make_response, json, request
from twilio.rest import Client

import logging
import helper
import traceback
import string
import random

# Account Sid and Auth Token
ACCOUNT_SID = 'ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
AUTH_TOKEN = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
APP_PHONE_NUMBER = '+14*********'
ADMIN_PHONE_NUMBER = ['+16*********']

# In memory Maps to store
CONTACT_MAP = {}
EVENTS_MAP = {}
ATTENDEE_LIST = []
CONTACT_DEFAULT_MAP = {
    "anyAllergy": 'No',
    "anyDietaryRestrictions": 'No',
    "mealPreference": 'No Preference'
}

# Messaged Constant
NO_ACCESS_MESSAGE = 'Sorry, you do have access to Admin Operations.\n\nYou can do operations like get your events list, event details and customize catering.'
ADD_ATTENDEE_MESSAGE = 'Attendee added successfully 🎉🎉!\n\nWe have notified the attendee for all the scheduled events. '
ADD_ATTENDEE_DUPLICATE_MESSAGE = 'Attendee already exist in current attendees list.'
REMOVE_ATTENDEE_MESSAGE = 'Attendee removed successfully and have been notified for all the scheduled events.'
NO_EVENT_FOUND = 'No event found to be related with Event ID.'

app = Flask(__name__)
client = Client(ACCOUNT_SID, AUTH_TOKEN)
logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s %('
                                                                         'threadName)s : %(message)s')

# HEALTH CHECK
@app.route("/v1/status", methods=['POST'])
def health_check():
    return make_response(jsonify(helper.create_say_response('Service is UP and RUNNING')), 200)


# GET ATTENDEES
@app.route("/v1/event/attendees", methods=['POST'])
def get_attendees():
    try:
        twilio_data = request.form
        user_identifier = twilio_data['UserIdentifier']
        current_task = twilio_data['CurrentTask']
        logging.info("get_attendees :: UserIdentifier: " + user_identifier + "  CurrentTask: " + current_task)

        if current_task == 'get_attendees_list' and user_identifier in ADMIN_PHONE_NUMBER:
            return make_response(jsonify(get_attendees_response()), 200)
        else:
            return make_response(jsonify(helper.create_say_response(NO_ACCESS_MESSAGE)), 200)
    except:
        logging.info("get_attendees Exception:: " + traceback.format_exc())
        return make_response(jsonify(helper.create_redirect_response("task://service_down")), 200)


def get_attendees_response():
    out = ""
    if len(ATTENDEE_LIST) == 0:
        out = 'No attendee present in attendees list.\n\n'
    else:
        out = 'List of attendees attending all the events :\n\n'
        for phone_number in ATTENDEE_LIST:
            out = out + phone_number + "\n"
    out = out + "\nYou can add new attendee with : \n \n"
    out = out + "ADD ATTENDEE [Phone Number] \n"
    return helper.create_say_response(out)


# ADD ATTENDEE
@app.route("/v1/event/attendee/add", methods=['POST'])
def add_attendee():
    try:
        twilio_data = request.form
        user_identifier = twilio_data['UserIdentifier']
        current_task = twilio_data['CurrentTask']
        logging.info("create_event_redirect :: UserIdentifier: " + user_identifier + "  CurrentTask: " + current_task)
        if current_task == 'add_attendee' and user_identifier in ADMIN_PHONE_NUMBER:
            attendee_phone_number = '+' + twilio_data['Field_attendee_phone_number_Value']
            if attendee_phone_number in ATTENDEE_LIST:
                return make_response(jsonify(helper.create_say_response(ADD_ATTENDEE_DUPLICATE_MESSAGE)), 200)
            elif attendee_phone_number not in ATTENDEE_LIST:
                if attendee_phone_number not in CONTACT_MAP:
                    CONTACT_MAP[attendee_phone_number] = CONTACT_DEFAULT_MAP
                ATTENDEE_LIST.append(attendee_phone_number)
                if len(EVENTS_MAP) > 0:
                    send_sms('You have been added as attendee in below events:\n' + build_events_list(),
                             attendee_phone_number)
                    send_sms('To get more details Send GET EVENT [Event ID#]', attendee_phone_number)
                    send_sms('To customize your event catering send CUSTOMIZE MY CATERING', attendee_phone_number)
                return make_response(jsonify(helper.create_say_response(ADD_ATTENDEE_MESSAGE)), 200)
            print_maps()
        else:
            return make_response(jsonify(helper.create_say_response(NO_ACCESS_MESSAGE)), 200)
    except:
        logging.info("add_attendee Exception:: " + traceback.format_exc())
        return make_response(jsonify(helper.create_redirect_response("task://service_down")), 200)


# CREATE EVENT REDIRECT
@app.route("/v1/event/create/check", methods=['POST'])
def create_event_redirect():
    try:
        twilio_data = request.form
        user_identifier = twilio_data['UserIdentifier']
        current_task = twilio_data['CurrentTask']
        logging.info("create_event_redirect :: UserIdentifier: " + user_identifier + "  CurrentTask: " + current_task)
        if current_task == 'create_event_check' and user_identifier in ADMIN_PHONE_NUMBER:
            return make_response(jsonify(helper.create_redirect_response("task://create_event")), 200)
        else:
            return make_response(jsonify(helper.create_say_response(NO_ACCESS_MESSAGE)), 200)
    except:
        return make_response(jsonify(helper.create_redirect_response("task://service_down")), 200)


# SAVE EVENT
@app.route("/v1/event/create", methods=['POST'])
def create_event():
    try:
        twilio_data = request.form
        memory_json = twilio_data['Memory']
        memory = json.loads(memory_json)
        logging.info("create_event :: " + json.dumps(memory, indent=4, sort_keys=True))

        event_location = memory['twilio']['collected_data']['create_event']['answers']['event_location']['answer']
        event_date = memory['twilio']['collected_data']['create_event']['answers']['event_date']['answer']
        event_time = memory['twilio']['collected_data']['create_event']['answers']['event_time']['answer']
        event_subject = memory['twilio']['collected_data']['create_event']['answers']['event_subject']['answer']
        event_organizer = memory['twilio']['collected_data']['create_event']['answers']['event_organizer']['answer']
        event_package = memory['twilio']['collected_data']['create_event']['answers']['event_package']['answer']

        event_details = {
            "eventId": id_generator(),
            "eventLocation": event_location,
            "eventDate": event_date,
            "eventTime": event_time,
            "eventSubject": event_subject,
            "eventOrganizer": event_organizer,
            "eventPackage": event_package,
        }

        EVENTS_MAP[event_details["eventId"]] = event_details
        for to_number in ATTENDEE_LIST:
            message = send_sms('Ahoy ! You have been added to event ID#' + event_details[
                "eventId"] + '. You can customize your meals for this event.\n\nTo get more details Send GET EVENT ['
                             'Event ID#]', to_number)
        return make_response(jsonify(helper.create_say_response('Event has been created with ID#' + event_details[
            "eventId"] + ' and all attendees has been notified.\n\nTo get more details Send GET EVENT [Event ID#]')),
                             200)
    except:
        logging.info("create_event Exception:: " + traceback.format_exc())
        return make_response(jsonify(helper.create_redirect_response("task://service_down")), 200)


# GET EVENT
@app.route("/v1/event/get", methods=['POST'])
def get_event():
    try:
        twilio_data = request.form
        user_identifier = twilio_data['UserIdentifier']
        event_id = twilio_data['Field_event_id_Value']
        logging.info("get_event Event ID :: " + event_id)
        if event_id in EVENTS_MAP:
            event = EVENTS_MAP[event_id]
            msg = " Event ID#" + event['eventId'] + ' has been scheduled for ' + event['eventDate'] + ' at ' + event[
                'eventTime'] + ' in ' + event['eventLocation'] + '. This event is organized by ' + event[
                      'eventOrganizer'] + ' and subject of event is ' + event['eventSubject'] + '.'
            if user_identifier in CONTACT_MAP and CONTACT_MAP[user_identifier]['mealPreference'] != 'No Preference':
                msg = msg + CONTACT_MAP[user_identifier]['mealPreference'] + ' meal will be provided in food catering.'
            else:
                msg = msg + event['eventPackage'] + ' meal will be provided in food catering.'
            return make_response(jsonify(helper.create_say_response(msg)), 200)
        else:
            return make_response(jsonify(helper.create_say_response(NO_EVENT_FOUND)), 200)
    except:
        logging.info("get_event Exception:: " + traceback.format_exc())
        return make_response(jsonify(helper.create_redirect_response("task://service_down")), 200)


# GET EVENT LIST
@app.route("/v1/event/get/list", methods=['POST'])
def get_event_list():
    try:
        if len(EVENTS_MAP) == 0:
            msg = 'No scheduled event at this moment.\n\n'
            return make_response(jsonify(helper.create_say_response(msg)), 200)
        else:
            return make_response(jsonify(helper.create_say_response(
                'Your list of Event ID#:\n' + build_events_list() + '\n\nTo get more details Send GET EVENT [Event ID#]')),
                                 200)
    except:
        logging.info("get_event_list Exception:: " + traceback.format_exc())
        return make_response(jsonify(helper.create_redirect_response("task://service_down")), 200)


# GET ATTENDEE DIET
@app.route("/v1/event/get/attendees/diet", methods=['POST'])
def get_attendees_diet():
    try:
        twilio_data = request.form
        user_identifier = twilio_data['UserIdentifier']
        current_task = twilio_data['CurrentTask']
        logging.info("get_attendees_diet :: UserIdentifier: " + user_identifier + "  CurrentTask: " + current_task)
        if current_task == 'get_attendees_diet' and user_identifier in ADMIN_PHONE_NUMBER:
            if len(ATTENDEE_LIST) == 0:
                return make_response(jsonify(helper.create_say_response('No attendee present in attendees list.')), 200)
            else:
                resp = "ATTENDEE | ALLERGIC | MEAL\n\n"
                resp = resp + build_attendee_diet()
                return make_response(jsonify(helper.create_say_response(resp)), 200)
        else:
            return make_response(jsonify(helper.create_say_response(NO_ACCESS_MESSAGE)), 200)
    except:
        logging.info("get_attendees_diet Exception:: " + traceback.format_exc())
        return make_response(jsonify(helper.create_redirect_response("task://service_down")), 200)


# UPDATE DIET RESTRICTION
@app.route("/v1/event/attendee/update", methods=['POST'])
def update_diet_preference():
    try:
        twilio_data = request.form
        user_identifier = twilio_data['UserIdentifier']
        memory_json = twilio_data['Memory']
        memory = json.loads(memory_json)
        logging.info("create_event :: " + json.dumps(memory, indent=4, sort_keys=True))
        if user_identifier not in CONTACT_MAP:
            CONTACT_MAP[user_identifier] = CONTACT_DEFAULT_MAP

        attendee_pref = CONTACT_MAP[user_identifier]
        attendee_pref['anyAllergy'] = \
            memory['twilio']['collected_data']['custom_attendee_diet']['answers']['any_allergy']['answer']
        attendee_pref['anyDietaryRestrictions'] = \
            memory['twilio']['collected_data']['custom_attendee_diet']['answers']['any_dietary_restrictions']['answer']
        attendee_pref['mealPreference'] = \
            memory['twilio']['collected_data']['custom_attendee_diet']['answers']['meal_preference']['answer']
        return make_response(jsonify(helper.create_say_response('We have saved your customization 👍.\n\nThank you '
                                                                'for submitting your meal preference.')), 200)
    except:
        logging.info("create_event Exception:: " + traceback.format_exc())
        return make_response(jsonify(helper.create_redirect_response("task://service_down")), 200)


def send_sms(message_body, to):
    message = client.messages.create(body=message_body, from_=APP_PHONE_NUMBER, to=to)
    return message


def id_generator(size=6, chars=string.digits):
    return ''.join(random.choice(chars) for x in range(size))


def build_events_list():
    msg = "\n"
    for event in EVENTS_MAP.keys():
        msg = msg + event + '\n'
    return msg


def build_attendee_diet():
    msg = ""
    for attendee in ATTENDEE_LIST:
        msg = msg + attendee + ' | ' + CONTACT_MAP[attendee]['anyAllergy'] + ' | ' + CONTACT_MAP[attendee][
            'mealPreference'] + '\n'
    return msg


def print_maps():
    logging.info("EVENTS_MAP :: " + json.dumps(EVENTS_MAP, indent=4, sort_keys=True))
    logging.info("CONTACT_MAP :: " + json.dumps(CONTACT_MAP, indent=4, sort_keys=True))
    logging.info("ATTENDEE_LIST :: " + str(ATTENDEE_LIST))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8500, debug=True)
