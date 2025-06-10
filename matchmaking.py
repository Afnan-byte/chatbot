users = {}
waiting_males = []
waiting_females = []

def set_gender(user_id, gender):
    users[user_id] = {"gender": gender, "state": "idle", "partner": None}

def start_search(user_id):
    gender = users[user_id]["gender"]
    if gender == "male":
        return match(user_id, waiting_females, waiting_males)
    else:
        return match(user_id, waiting_males, waiting_females)

def match(user_id, opposite_queue, same_queue):
    if opposite_queue:
        partner_id = opposite_queue.pop(0)
        users[user_id]["state"] = "chatting"
        users[partner_id]["state"] = "chatting"
        users[user_id]["partner"] = partner_id
        users[partner_id]["partner"] = user_id
        return partner_id
    else:
        same_queue.append(user_id)
        users[user_id]["state"] = "searching"
        return None

def end_chat(user_id):
    partner_id = users[user_id].get("partner")
    if partner_id:
        users[partner_id]["partner"] = None
        users[partner_id]["state"] = "idle"
    users[user_id]["partner"] = None
    users[user_id]["state"] = "idle"
    return partner_id
