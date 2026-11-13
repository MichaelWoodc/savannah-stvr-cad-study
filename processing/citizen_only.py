"""Analysis policy: citizen initiation only, excluding proactive patrol/stop labels."""
PROACTIVE = r'PATROL|CRIME\s*HOT\s*SPOT|TRAFFIC\s*STOP|SUBJECT\s*STOP|PARK\s*/\s*WALK\s*/\s*TALK|COMMUNITY\s*ENGAGEMENT'

def select(frame, initiation='initiation', call_type='type'):
    return frame[frame[initiation].eq('Cit Initiated') & ~frame[call_type].str.contains(PROACTIVE,case=False,na=False,regex=True)].copy()
