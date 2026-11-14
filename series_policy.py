"""Episode order and conservative next-up timing; no inferred credit boundaries."""
def episode_numbers(record):
    explicit=record.get('episodeNumbers')
    if not isinstance(explicit,list):
        explicit=[int(n) for n in str(record.get('allEp') or '').split(',') if n.strip().isdigit()]
        if not explicit:explicit=range(1,min(10000,int(record.get('maxEp') or 0))+1)
    return sorted({int(n) for n in explicit if str(n).isdigit() and int(n)>0})

def next_episode(seasons,season,episode):
    for record in sorted(seasons,key=lambda item:int(item.get('se') or 0)):
        number=int(record.get('se') or 0)
        if number<max(1,int(season)):continue
        choices=[ep for ep in episode_numbers(record) if number>season or ep>episode]
        if choices:return number,choices[0]
    return None

def next_up_at(duration_ms,metadata=None):
    duration_ms=int(duration_ms or 0)
    if duration_ms<=0:return None
    metadata=metadata or {}
    marker=metadata.get('creditsStartMs')
    if marker is not None:
        try:
            marker=int(marker)
            if duration_ms//2<marker<duration_ms:return marker
        except (ValueError,TypeError):pass
    # Offer a prompt; never automatically skip an unknown ending/credits boundary.
    return max(0,duration_ms-min(30000,max(5000,duration_ms//10)))
