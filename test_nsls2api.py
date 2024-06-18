import httpx
import time
import nsls2api_lib

base_url = "https://api.nsls2.bnl.gov/v1"

cycle = "2022-3"
proposals_api = nsls2api_lib.get_proposals_from_cycle(cycle)
print(f"total proposals for cycle {cycle}: {len(proposals_api)}")

username = "jaishima"
datasessions_api = nsls2api_lib.get_data_sessions_for_user(username)
for data_session in datasessions_api['data_sessions']:
    print(f"data session: {data_session}")

facility_name = "nsls2"
facilities_cycles = nsls2api_lib.get_cycles_from_facility(facility_name)
print(f"cycles for facility {facility_name}:"),
for cycle in facilities_cycles["cycles"]:
    print(cycle,)

beamline = nsls2api_lib.get_beamline("xfp")
for item in beamline:
    print(item, beamline[item])

proposal = nsls2api_lib.get_proposal_info(312064)  # FMX commissioning proposal
proposal_id = proposal['proposal_id']
print(f"proposalID: {proposal_id}")
print(f'users for proposal {proposal_id}: {nsls2api_lib.get_users_from_proposal(proposal_id)}')
print(f'directories: {nsls2api_lib.get_directories_from_proposal(proposal_id)}')
print(f'full info on proposal: {nsls2api_lib.get_proposal_info(proposal_id)}')
