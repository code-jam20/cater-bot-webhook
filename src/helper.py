# Helper class to generate Autopilot Actions
def create_say_response(say):
    response = {
        "actions": [
            {
                "say": say
            }
        ]
    }
    return response


def create_say_redirect_response(say, redirect):
    response = {
        "actions": [
            {
                "say": say
            },
            {
                "redirect": redirect
            }
        ]
    }


def create_redirect_response(redirect):
    response = {
        "actions": [
            {
                "redirect": redirect
            }
        ]
    }
    return response


