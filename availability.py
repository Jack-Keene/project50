import psycopg2
from tempfile import mkdtemp
from config import config
from datetime import time, date, datetime, timedelta



# Initialise Postgres Connection
def connect(sql, values = ""):
    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # read connection parameters
        params = config()

        # connect to the PostgreSQL server
        # print('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)
		
        # create a cursor
        cur = conn.cursor()
        cur.execute(sql , values)
        # execute a statement
        conn.commit()

        # display the PostgreSQL database server version
        db_version = cur.fetchall()
        return db_version
        # print(db_version)
       
	# close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            # print('Database connection closed.')
    # return db_version

def ramps():
    ramps = connect("SELECT * FROM ramp")
    return ramps

def dealer(dealer_code):
    dealer = connect("SELECT DISTINCT dealer_code, open_time, close_time FROM dealer WHERE dealer_code = %s", (dealer_code, ))
    return dealer

def availability(ramp_id, start_time, end_time, day):
    connect("""INSERT INTO availability (availability, start_time, end_time, ramp_id, day) VALUES (%s, %s, %s, %s, %s) """, (("True", start_time, end_time, ramp_id, day,)))


def add_slots():
    ramp_id = ramps()
    for ramp in range(len(ramp_id)):
        # dealer_info = dealer(ramp_id[ramp][1])
        # dealer_code = dealer_info[0][0]
        # loop through hours in day and add row for ramp id and dealer
        for day in range(30):
            add_date = date.today() +timedelta(days = 1) + timedelta(days = day)
            for hour in range (23):
                availability(ramp+1, time(hour,0), time(hour+1,0), add_date)
    return None


def main():
    add_slots()

if __name__ == "__main__":
    main()