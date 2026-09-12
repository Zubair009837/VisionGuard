from datetime import datetime, timedelta
from .config import NVRS

def risk_snapshot():
    from . import crud
    cams=crud.get_cached_cameras(online_only=False)
    result=[]
    for n in NVRS:
        name=n['name']; cc=[c for c in cams if c.get('nvr')==name]; offline=sum(1 for c in cc if str(c.get('status','')).lower()!='online')
        score=0; reasons=[]
        if cc and offline/len(cc)>.10: score+=30; reasons.append(f'{offline}/{len(cc)} cameras not online')
        try:
            from .recording_monitor import get_active_recording_losses
            losses=sum(1 for x in get_active_recording_losses() if x.get('nvr')==name)
            if losses: score+=min(50, losses*10); reasons.append(f'{losses} active recording-loss channels')
        except Exception: pass
        try:
            from .nvr_control_center import _load
            events=_load().get('events',[]); recent=[e for e in events if e.get('nvr')==name and e.get('type') in ('NVR_TIME_DRIFT','NVR_TIME_CHANGED')]
            if recent: score+=10; reasons.append('recent NVR time drift/change')
        except Exception: pass
        result.append({'nvr':name,'ip':n['ip'],'score':min(100,score),'level':'HIGH' if score>=70 else 'MEDIUM' if score>=40 else 'LOW','reasons':reasons})
    return {'generated_at':datetime.now().isoformat(),'items':result}
