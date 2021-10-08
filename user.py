# Define levels of access
ACCESS = {
    'guest': 0,
    'Customer': 1,
    'Dealer': 2,
    'Manufacturer': 3
}

ZONE = ["N1", "N2", "S1", "S2"]

# initialise user class with levels of access
class User():
    def __init__(self,id,  first_name, last_name, email, username, hashed, postcode, street, number, phone_number, type = ACCESS['Customer']):

        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.username = username
        self.hashed = hashed
        self.postcode = postcode
        self.street = street
        self.number = number
        self.phone_number = phone_number
        self.type = type
    
    def is_dealer(self):
        return self.type == ACCESS['Dealer']

    def is_manufacturer(self):
        return self.type == ACCESS('Manufacturer')

    def allowed(self, access_level):
        return self.type == access_level