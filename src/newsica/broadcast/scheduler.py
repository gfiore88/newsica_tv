import datetime
from schedule_generator import get_current_schedule, generate_schedule

def get_wallclock_schedule_key():
    schedule_data = get_current_schedule()
    times = sorted(schedule_data.keys())
    current_time_str = datetime.datetime.now().strftime("%H:%M")
    current_time_key = times[0]
    for t in times:
        if t <= current_time_str:
            current_time_key = t
        else:
            break
    return current_time_key

def schedule_deadline(next_time_key):
    now = datetime.datetime.now()
    hour, minute = [int(part) for part in next_time_key.split(":")]
    deadline = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if deadline <= now:
        deadline += datetime.timedelta(days=1)
    return deadline

def get_current_block_info(manual_block_override_index=None):
    schedule_data = get_current_schedule()
    times = sorted(schedule_data.keys())
    
    if manual_block_override_index is None:
        current_time_key = get_wallclock_schedule_key()
        current_active_index = times.index(current_time_key)
    else:
        current_active_index = manual_block_override_index
        
    current_time_key = times[current_active_index]
    block = schedule_data[current_time_key]
    
    next_index = (current_active_index + 1) % len(times)
    next_time_key = times[next_index]
    next_block = schedule_data[next_time_key]
    
    return block.get("type", "music_only"), block.get("title", ""), next_block.get("title", ""), next_time_key, current_time_key, current_active_index

def get_next_block_info_for_key(current_time_key):
    try:
        schedule_data = get_current_schedule()
        times = sorted(schedule_data.keys())
        
        if current_time_key in times:
            current_idx = times.index(current_time_key)
            next_idx = (current_idx + 1) % len(times)
            next_time_key = times[next_idx]
            next_block = schedule_data[next_time_key]
            return next_block.get("type", "music_only"), next_block.get("title", ""), next_time_key
    except Exception as e:
        print(f"⚠️ Errore get_next_block_info_for_key: {e}")
    return "music_only", "", ""
