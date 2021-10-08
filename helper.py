
# adapted from https://blog.teclado.com/learn-python-defining-user-access-roles-in-flask/
from functools import wraps
from flask import url_for, request, redirect, session
from user import User
import os
import requests

def requires_access_level(access_level):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('user_id'):
                return redirect("/login")

            elif not session.get("access") >=  access_level:
                return redirect("/login")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def vehicle_lookup(registration):
    # Use DVLA API to lookup vehicle information and history

    url = "https://driver-vehicle-licensing.api.gov.uk/vehicle-enquiry/v1/vehicles"
    payload = "{\n\t\"registrationNumber\": \"" + registration + "\"\n}"

    headers = {
            'x-api-key': 'XmIieBuFvltjahQmOzrc665g39ePuF467hDAt6j7',
            'Content-Type': 'application/json'
                }

    response = requests.request("POST", url, headers=headers, data = payload)
    vehicle_details = response.json()
    print(vehicle_details)

    if 'errors' in vehicle_details:
        return None
    else:
        return {
            "make": vehicle_details['make'],
            "model": vehicle_details['colour'],
            "year": vehicle_details['yearOfManufacture'],
            "mot_date": vehicle_details['motExpiryDate']
        }