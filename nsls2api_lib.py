import httpx
import time

base_url = "https://api.nsls2.bnl.gov/v1"

ispyb_instruments = ("AMX", "FMX", "NYX")

def is_ispyb_instrument(instruments):
    for instrument in instruments:
        if instrument in ispyb_instruments:
            return True
    return False

def get_from_api(url):
    if url:
        response = httpx.get(f"{base_url}/{url}")
        if response.status_code == httpx.codes.OK:
            return response.json()
        raise RuntimeError(f"failed to get value from {url}. response code: {response.status_code}")
    else:
        raise ValueError("url cannot be empty")

def get_all_cycles():
    return get_from_api(f"facility/nsls2/cycles")
def get_proposals_from_cycle(cycle):
    return get_from_api(f"facility/nsls2/cycle/{cycle}/proposals")['proposals']
def get_usernames_from_proposal(proposal_id):
    return set(get_from_api(f"proposal/{proposal_id}/usernames")['usernames'])
def get_users_from_proposal(proposal_id):
    return get_from_api(f"proposal/{proposal_id}/users")
def get_directories_from_proposal(proposal_id):
    return get_from_api(f"proposal/{proposal_id}/directories")
def get_proposal_info(proposal_id):
    return get_from_api(f"proposal/{proposal_id}")['proposal']

def get_active_safs_for_proposal(proposal_id):  # currently unused
    safs = get_all_proposals(proposal_id)['safs']

def get_all_active_safs_in_current_cycle(cycle="2023-1"):  # currently unused
    proposals = get_proposals_from_cycle(cycle)
    for proposal in proposals:
        safs = get_all_proposals(proposal.id)['safs']

def get_proposals_for_instrument(cycle="2023-1", instrument="FMX"):
    proposals_on_instrument = []
    proposals = get_proposals_from_cycle(cycle)
    for proposal_num in proposals:
        proposal = get_proposal_info(proposal_num)
        if instrument in proposal['instruments']:
            proposals_on_instrument.append(proposal_num)
    return proposals_on_instrument

def get_data_sessions_for_user(username):
    sessions = get_from_api(f"data-session/{username}")
    return sessions

def get_cycles_from_facility(facilityname):
    cycles = get_from_api(f"facility/{facilityname}/cycles")
    return cycles

def get_beamline(beamline):
    beamline = get_from_api(f"beamline/{beamline}")
    return beamline
def get_current_cycle():
    return get_from_api(f"facility/nsls2/cycles/current")["cycle"]
