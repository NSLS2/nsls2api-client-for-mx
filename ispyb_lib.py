import ispyb.factory
import nsls2api_lib
from datetime import datetime
import time
import mysql.connector
import os
import logging
logger = logging.getLogger(__name__)

ispyb_db = os.getenv('ISPYB_DB', "ispyb")
logger.info(f"Making ISPyB connection using database: {ispyb_db}")
conn = ispyb.open(f"/etc/ispyb/{ispyb_db}Config.cfg")
cnx = conn.conn
cursor = cnx.cursor()
core = ispyb.factory.create_data_area(ispyb.factory.DataAreaType.CORE, conn)

def queryDB(q):
  cursor.execute(q)
  try:
    return list(cursor.fetchall())
  except TypeError:
    return 0

def queryOneFromDB(q):
  cursor.execute(q)
  try:
    return list(cursor.fetchone())[0]
  except TypeError:
    return 0

# get list numbers from a queryDB() call
# be able to handle input from a query result or raw list
def get_unique_ids(id_list):
    id_set = set()
    for _id in id_list:
        if type(_id) == tuple:
            id_set.add(_id[0])
        elif type(_id) == int:
            id_set.add(_id)
    return list(id_set)

# works for query results
def get_in_string(ids):
    if len(ids)> 1:
        multi_id_string = ""
        for _id in get_unique_ids(ids):
            id_string = str(_id)
            multi_id_string += f"'{id_string}', "
        return multi_id_string[:-2]  # get rid of trailing comma
    else:
        return f"'{str(ids[0])}'"

def get_ispyb_proposal_ids():
    '''
    Get all proposals in the ISPyB database by starting from
    BLSessions
    '''
    # go through all of Session_has_person and get all BLSessions
    query = "SELECT sessionId FROM Session_has_Person;"
    session_ids = queryDB(query)
    session_id_string = ""
    if len(session_ids)> 1:
        for session_id in get_unique_ids(session_ids):
            session_str = str(session_id)
            session_id_string += f"'{session_str}', "
        session_id_string = session_id_string[:-2]
    else:
        session_id_string = f"'{session_ids[0]}'"
    # get proposals
    query = f"SELECT proposalId from BLSession where sessionId in ({session_id_string});"
    proposal_ids = queryDB(query)
    return get_unique_ids(proposal_ids)

def get_proposal_numbers(proposal_ids):
    query = f"SELECT proposalNumber from Proposal where proposalId in ({get_in_string(proposal_ids)});"
    proposal_nums = queryDB(query)
    return get_unique_ids(proposal_nums)


def get_session_ids_for_proposal(proposal_number):
    query = f"SELECT proposalId from Proposal where proposalNumber={proposal_number}"
    proposal_id = queryOneFromDB(query)
    query = f"SELECT sessionId FROM BLSession where proposalId={proposal_id}"  # note difference of what we call proposal_id vs BLSession's name, which is proposal_number
    session_ids = queryDB(query)
    return session_ids

def remove_all_usernames_for_proposal(proposal_id, dry_run=True):
    '''
    Not within the name is the fact that associations with visits
    (sessions/BLSessions) are also removed here
    '''
    if dry_run:
        logger.info(f"Clearing usernames for proposal {proposal_id}")
    session_ids = get_session_ids_for_proposal(proposal_id)
    people_in_sessions = set()
    for session_id in session_ids:
        query = f"SELECT personId FROM Session_has_Person WHERE sessionId={session_id[0]}"
        people_in_session = queryDB(query)
        for person in people_in_session:
            # TODO something to show the username of this person?
            people_in_sessions.add(person)
    if dry_run:
        logger.info(f"Dry run: remove usernames from Session_has_Person:",)
        people_name = set()
        for person in people_in_sessions:
            query = f"SELECT login from Person where personId={person[0]}"
            name = queryOneFromDB(query)
            people_name.add(name)
        logger.info(f"{people_name}", )
    # clear all Session_has_Person for the proposal
    if not dry_run:
        for session_id in session_ids:
            for person in people_in_sessions:
                query = f"DELETE FROM Session_has_Person where sessionId={session_id[0]} AND personId={person[0]}"
                try:
                    delete_session_has_person = queryDB(query)
                except mysql.connector.errors.ProgrammingError as e:
                    logger.exception(f"Problem with proposal {proposal_id}, session {session_id}, person {person}")


def create_person(first_name, last_name, login, is_pi, dry_run=True):
    query = f"INSERT INTO Person (givenName, familyName, login) VALUES('{first_name}', '{last_name}', '{login}')"
    if not dry_run:
        queryDB(query)
        person_id = queryOneFromDB(f"SELECT personId from Person where login='{login}'")
    else:
        person_id = -1
    return person_id


def sanitize_name(name):
    intermediate = [ ch for ch in name if ch.isalpha() ]
    return "".join(intermediate)

def create_people(proposal_id, current_usernames, users_info, dry_run=True):
    '''
    Only way to get information about people in the current API is to
    get it from the proposal. This should change in the next version
    of the nslsii API
    '''
    person_ids = set()
    for username in current_usernames:
        query = f"SELECT personId from Person where login='{username}'"
        person_id = queryDB(query)
        first_name = None
        last_name = None
        is_pi = False
        if not person_id:  # the Person doesn't exist in ISPyB yet
            # extract first and last names from proposal info
            for user_info in users_info:
                if username == user_info['username']:
                    first_name = user_info['first_name']
                    last_name = user_info['last_name']
                    is_pi = user_info['is_pi']
                    break
            if first_name and last_name:
                try:
                    person_id = create_person(sanitize_name(first_name), sanitize_name(last_name), username, is_pi, dry_run)
                    logger.info(f"added new person {username} with id: {person_id}")
                except mysql.connector.errors.ProgrammingError as e:
                    logger.exception(f"Error while trying to create new person {username} first name: {first_name} last name: {last_name} is_pi: {is_pi} with id: {person_id} {e}")
                    continue
            else:
                raise RuntimeError(f"Username {person_id} not found, aborting!")
        else:
            logger.debug("using existing person")
            person_id = person_id[0][0]
        person_ids.add(person_id)
    return person_ids


def add_usernames_for_proposal(proposal_code, current_usernames, users_info, beamline, dry_run=True):
    if type(current_usernames) != set:
        raise ValueError("current usernames must be a set")
    logger.info(f"add_usernames_for_proposal: users to add ({len(current_usernames)}): {current_usernames}")
    if dry_run:
        logger.info('dry run, stopping')
        return
    user_ids = create_people(proposal_code, current_usernames, users_info, dry_run)  # TODO see how to get PI status from nsls2api
    proposal_id = create_proposal(proposal_code, dry_run)
    session_ids = get_session_ids_for_proposal(proposal_code)
    if len(session_ids) == 0:
        session_id = [create_session(proposal_id, 1, beamline, dry_run)]
    for person_login in current_usernames:
        for session_id in session_ids:
            person_id = is_person(person_login)
            query = f"SELECT personId from Session_has_Person WHERE (personId, sessionId) in (({person_id}, {session_id[0]}))"
            if not dry_run:
                try:
                    check_person_id = queryOneFromDB(query)
                    if not check_person_id:
                        raise Exception("No person")
                    return
                except Exception as e:
                    print(f"Exception while querying Session_has_Person {e}: Most likely because this association has not been made yet. continuing")
            query=f"INSERT INTO Session_has_Person (sessionId, personId, role, remote) values ({session_id[0]}, {person_id}, 'Co-Investigator', 1)"
            if not dry_run:
                queryDB(query)


def reset_users_for_proposal(proposal_id, dry_run=True):
    ''' given a proposal id, take all of the users off an existing set of visits
        in ispyb and add the current users in '''
    # first, clear all existing usernames for the proposal_id in ISPyB
    # alternative, get usernames here, then remove/add as necessary at the bottom
    remove_all_usernames_for_proposal(proposal_id, dry_run)
    # next, get the users who should be on the current proposal
    add_users_for_proposal(proposal_id, dry_run)


def add_users_for_proposal(proposal_id, session_number=1, beamline="amx", dry_run=True):
    current_usernames = nsls2api_lib.get_usernames_from_proposal(proposal_id)
    try:
        user_info = nsls2api_lib.get_users_from_proposal(proposal_id)['users']
        # TODO consider what should happen if old proposals have no users
        add_usernames_for_proposal(proposal_id, set(current_usernames), user_info, beamline, dry_run=dry_run)
    except KeyError as e:
        logger.exception(f"Problem {e} with getting user info from proposal {proposal_id}. there may be no users associated with the proposal. continuing")


def proposal_id_from_proposal(propNum):
  q = ("select proposalId from Proposal where proposalNumber = " + str(propNum))
  return (queryOneFromDB(q))


def max_visit_num_from_proposal(propNum):
  propID = proposal_id_from_proposal(propNum)
  q = ("select max(visit_number) from BLSession where proposalId = " + str(propID))
  return (queryOneFromDB(q))

def setup_proposal(proposal, users):
    # if doesn't exist, make it
    #   highest visit number is 1
    # find highest visit number
    # create newest proposal (highest number)
    # add users to proposal
    # add users to session
    pass

def is_person(username):
    query = f"SELECT personId from Person where login='{username}'"
    return queryOneFromDB(query)


def get_proposal_info_from_nsls2api(proposal_id):
    # get info useful for creating proposal
    # create people in proposal if they haven't already been created
    value = {}
    info = nsls2api_lib.get_proposal_info(proposal_id)
    for user in info["users"]:
        if not is_person(user["username"]):
            user_id = create_person(user["first_name"], user["last_name"], user["username"], user["is_pi"], dry_run=False)
        if user["is_pi"]:
            value["username"] = user["username"]
    if value.get("username", None) == None:
        print("This proposal has no PI associated with it!")
    # TODO is pass_type_id for mx/gu/pr? should we use these for proposal_type?
    value["proposal_type"] = "mx"
    value["title"] = info["title"]
    # TODO validate that user_id is available
    return value


def create_proposal(proposal_id, dry_run=True):
    # proposal code/type, PI, title
    # TODO currently, use first PI. decide how to handle multiple PIs
    # TODO check whether proposal already exists - skip if info is same, after creating users
    prop_info = get_proposal_info_from_nsls2api(proposal_id)
    user_id_query = f"SELECT personId from Person where login='{prop_info['username']}'"
    user_id = queryOneFromDB(user_id_query)
    try:
        test_proposal_id = queryOneFromDB(f"SELECT proposalId from Proposal where proposalNumber='{proposal_id}'")
        if not test_proposal_id:
            raise Exception("No proposal")
        # already exists, just return it
        return test_proposal_id
    except Exception as e:
        print(f"Exception while trying to check for existing Proposal: {e}. Typically, no Proposal exists yet")
    query = f"INSERT INTO Proposal (proposalCode, proposalNumber, proposalType, personId, title) VALUES('mx', {proposal_id}, 'mx', {user_id}, {prop_info['title'].isalpha()})"
    if not dry_run:
        queryDB(query)
        proposal_id = queryOneFromDB(f"SELECT proposalId from Proposal where proposalNumber='{proposal_id}'")
    else:
        proposal_id = -1
    return proposal_id


# the proposal_id here is a true proposal ID - currently, this value is actually the proposal number
def create_session(proposal_id, session_number, beamline_name, dry_run=True):
    current_datetime = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    try:
        sid = queryOneFromDB(f"SELECT sessionId from BLSession where proposalId='{proposal_id}' and visit_number='{session_number}'")
        if not sid:
            raise Exception("No session")
        return sid
    except Exception as e:
        print(f"Exception while trying to check for existing session: {e}. typically, no BLSession exists yet")
    query = f"INSERT INTO BLSession (proposalId, visit_number, beamLineName, startDate, endDate, comments) VALUES({proposal_id}, {session_number}, '{beamline_name}', '{current_datetime}', '{current_datetime}', 'For software testing')"
    if not dry_run:
        queryDB(query)
        sid = queryOneFromDB(f"SELECT sessionId from BLSession where proposalId='{proposal_id}' and visit_number='{session_number}'")
    else:
        sid = -1
    return sid
