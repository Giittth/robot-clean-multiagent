# 预定义场景
SCENARIOS = {
    "empty": {
        "start": (2, 2),
        "obstacles": [],
        "rooms": []
    },
    "small_map": {
        "start": (3, 3),
        "obstacles": [[5,5], [6,6], [7,7]],
        "rooms": []
    },
    "standard": {
        "start": (0, 0),  # 起点位于走廊中央
        "obstacles": [],
        "rooms": [
            # 走廊
            {"name": "hallway", "polygon": [[-7, -1], [8.5, -1], [8.5, 1], [-7, 1]], "entry_point": [0, 0], "center": [0, 0]},
            # 上侧房间（北侧，y=1~5）
            {"name": "room_north_1", "polygon": [[-7, 1], [-3.5, 1], [-3.5, 5], [-7, 5]], "entry_point": [-5.25, 1], "center": [-5.25, 3]},
            {"name": "room_north_2", "polygon": [[-3.5, 1], [0, 1], [0, 5], [-3.5, 5]], "entry_point": [-1.75, 1], "center": [-1.75, 3]},
            {"name": "room_north_3", "polygon": [[0, 1], [3.5, 1], [3.5, 5], [0, 5]], "entry_point": [1.75, 1], "center": [1.75, 3]},
            {"name": "room_north_4", "polygon": [[5, 1], [8.5, 1], [8.5, 5], [5, 5]], "entry_point": [7.25, 1], "center": [7.25, 3]},
            # 下侧房间（南侧，y=-5~-1）
            {"name": "room_south_1", "polygon": [[-7, -5], [-3.5, -5], [-3.5, -1], [-7, -1]], "entry_point": [-5.25, -1], "center": [-5.25, -3]},
            {"name": "room_south_2", "polygon": [[-3.5, -5], [0, -5], [0, -1], [-3.5, -1]], "entry_point": [-1.75, -1], "center": [-1.75, -3]},
            {"name": "room_south_3", "polygon": [[0, -5], [3.5, -5], [3.5, -1], [0, -1]], "entry_point": [1.75, -1], "center": [1.75, -3]},
            {"name": "room_south_4", "polygon": [[5, -5], [8.5, -5], [8.5, -1], [5, -1]], "entry_point": [7.25, -1], "center": [7.25, -3]},
            # 楼梯（位于走廊右侧上方）
            {"name": "stairs", "polygon": [[3.5, 1], [5, 1], [5, 2.5], [3.5, 2.5]], "entry_point": [4.25, 1], "center": [4.25, 1.75]},
            # 厕所（位于下侧最右侧下方）
            {"name": "toilet", "polygon": [[3.5, -1], [5, -1], [5, -3], [3.5, -3]], "entry_point": [4.25, -1], "center": [4.25, -4]}
        ]
    },
    "open_plan": {  # 开放式户型：客厅+餐厅+厨房连通，卧室独立
        "start": (0, 0),
        "obstacles": [[0,2], [1,2], [2,2]],
        "rooms": [
            {"name": "living_dining", "polygon": [[-4,-2], [4,-2], [4,2], [-4,2]], "entry_point": [0,-2], "center": [0,0]},
            {"name": "kitchen", "polygon": [[-4,2], [0,2], [0,6], [-4,6]], "entry_point": [-2,2], "center": [-2,4]},
            {"name": "bedroom", "polygon": [[2,2], [6,2], [6,6], [2,6]], "entry_point": [4,2], "center": [4,4]}
        ]
    },
    "apartment": {  # 两室一厅小户型
        "start": (0, 0),
        "obstacles": [],
        "rooms": [
            {"name": "living_room", "polygon": [[-3,-2], [3,-2], [3,3], [-3,3]], "entry_point": [0,-2], "center": [0,0.5]},
            {"name": "bedroom1", "polygon": [[-5,3], [-3,3], [-3,6], [-5,6]], "entry_point": [-4,3], "center": [-4,4.5]},
            {"name": "bedroom2", "polygon": [[1,3], [3,3], [3,6], [1,6]], "entry_point": [2,3], "center": [2,4.5]},
            {"name": "kitchen", "polygon": [[-5,-2], [-3,-2], [-3,0], [-5,0]], "entry_point": [-4,-2], "center": [-4,-1]},
            {"name": "bathroom", "polygon": [[3,-2], [5,-2], [5,0], [3,0]], "entry_point": [4,-2], "center": [4,-1]}
        ]
    },
    "villa": {  # 大别墅：多个房间分散
        "start": (0, 0),
        "obstacles": [],
        "rooms": [
            {"name": "living_room", "polygon": [[-2, -2], [2, -2], [2, 2], [-2, 2]], "entry_point": [0, -2], "center": [0, 0]},
            {"name": "bedroom2", "polygon": [[-6, -4], [-2, -4], [-2, 0], [-6, 0]], "entry_point": [-4, -2], "center": [-4, -2]},
            {"name": "dining_room", "polygon": [[2, -2], [6, -2], [6, 2], [2, 2]], "entry_point": [4, -2], "center": [4, 0]},
            {"name": "kitchen", "polygon": [[2, 2], [6, 2], [6, 6], [2, 6]], "entry_point": [4, 2], "center": [4, 4]},
            {"name": "master_bedroom", "polygon": [[-6, 2], [-2, 2], [-2, 8], [-6, 8]], "entry_point": [-4, 4], "center": [-4, 5]},
            {"name": "foyer", "polygon": [[-2, -2], [-2, -4], [2, -4], [2, -2]], "entry_point": [0, -2], "center": [0, -3]},
            {"name": "bathroom", "polygon": [[-4, 0], [-2, 0], [-2, 2], [-4, 2]], "entry_point": [-3, 0], "center": [-3, 1]}
        ]
    },
    "mansion": {
        "start": (0, 0),
        "obstacles": [],
        "rooms": [
            {"name": "foyer", "polygon": [[-3, -3], [3, -3], [3, 0], [-3, 0]], "entry_point": [0, -3], "center": [0, -1.5]},
            {"name": "living_room", "polygon": [[-6, 0], [6, 0], [6, 5], [-6, 5]], "entry_point": [0, 5], "center": [0, 2.5]},
            {"name": "dining_room", "polygon": [[-6, -3], [3, -3], [3, 0], [-6, 0]], "entry_point": [-1.5, -3], "center": [-1.5, -1.5]},
            {"name": "kitchen", "polygon": [[3, -6], [6, -6], [6, 0], [3, 0]], "entry_point": [4.5, -3], "center": [4.5, -3]},
            {"name": "master_bedroom", "polygon": [[-6, 5], [-3, 5], [-3, 9], [-6, 9]], "entry_point": [-4.5, 5], "center": [-4.5, 7]},
            {"name": "guest_bedroom", "polygon": [[-2, 5], [2, 5], [2, 9], [-2, 9]], "entry_point": [0, 5], "center": [0, 7]},
            {"name": "study", "polygon": [[6, 5], [8, 5], [8, 9], [6, 9]], "entry_point": [7, 5], "center": [7, 7]},
            {"name": "bathroom", "polygon": [[3, -6], [6, -6], [6, -8], [3, -8]], "entry_point": [4.5, -6], "center": [4.5, -7]},
            {"name": "garage", "polygon": [[-6, -6], [-3, -6], [-3, -8], [-6, -8]], "entry_point": [-4.5, -6], "center": [-4.5, -7]},
        ]
    },
    "office": {
        "start": (0, 0),
        "obstacles": [],
        "rooms": [
            {"name": "open_workspace", "polygon": [[-5, -3], [5, -3], [5, 4], [-5, 4]], "entry_point": [0, -3], "center": [0, 0.5]},
            {"name": "meeting_room_a", "polygon": [[-5, 4], [-1, 4], [-1, 7], [-5, 7]], "entry_point": [-3, 4], "center": [-3, 5.5]},
            {"name": "meeting_room_b", "polygon": [[1, 4], [5, 4], [5, 7], [1, 7]], "entry_point": [3, 4], "center": [3, 5.5]},
            {"name": "kitchenette", "polygon": [[-5, -3], [-2, -3], [-2, -5], [-5, -5]], "entry_point": [-3.5, -3], "center": [-3.5, -4]},
            {"name": "restroom", "polygon": [[3, -3], [5, -3], [5, -5], [3, -5]], "entry_point": [4, -3], "center": [4, -4]},
        ]
    },
    "studio": {
        "start": (0, 0),
        "obstacles": [[1,1]],
        "rooms": [
            {"name": "living_sleeping", "polygon": [[-3, -2], [3, -2], [3, 3], [-3, 3]], "entry_point": [0, -2], "center": [0, 0.5]},
            {"name": "bathroom", "polygon": [[-3, 3], [0, 3], [0, 5], [-3, 5]], "entry_point": [-1.5, 3], "center": [-1.5, 4]},
            {"name": "kitchen", "polygon": [[0, 3], [3, 3], [3, 5], [0, 5]], "entry_point": [1.5, 3], "center": [1.5, 4]},
        ]
    },
    "school_floor": {
        "start": (0, -1),
        "obstacles": [],
        "rooms": [
            {"name": "corridor", "polygon": [[-6, -1], [6, -1], [6, 1], [-6, 1]], "entry_point": [0, -1], "center": [0, 0]},
            {"name": "classroom_101", "polygon": [[-6, 1], [-2, 1], [-2, 5], [-6, 5]], "entry_point": [-4, 1], "center": [-4, 3]},
            {"name": "classroom_102", "polygon": [[-2, 1], [2, 1], [2, 5], [-2, 5]], "entry_point": [0, 1], "center": [0, 3]},
            {"name": "classroom_103", "polygon": [[2, 1], [6, 1], [6, 5], [2, 5]], "entry_point": [4, 1], "center": [4, 3]},
            {"name": "classroom_104", "polygon": [[-6, -5], [-2, -5], [-2, -1], [-6, -1]], "entry_point": [-4, -1], "center": [-4, -3]},
            {"name": "classroom_105", "polygon": [[-2, -5], [2, -5], [2, -1], [-2, -1]], "entry_point": [0, -1], "center": [0, -3]},
            {"name": "classroom_106", "polygon": [[2, -5], [6, -5], [6, -1], [2, -1]], "entry_point": [4, -1], "center": [4, -3]},
        ]
    },
    "restaurant": {
        "start": (0, 0),
        "obstacles": [],
        "rooms": [
            {"name": "dining_hall", "polygon": [[-5, -3], [5, -3], [5, 4], [-5, 4]], "entry_point": [0, -3], "center": [0, 0.5]},
            {"name": "kitchen", "polygon": [[-5, 4], [-1, 4], [-1, 7], [-5, 7]], "entry_point": [-3, 4], "center": [-3, 5.5]},
            {"name": "storage", "polygon": [[1, 4], [5, 4], [5, 7], [1, 7]], "entry_point": [3, 4], "center": [3, 5.5]},
            {"name": "restroom", "polygon": [[-5, -3], [-2, -3], [-2, -5], [-5, -5]], "entry_point": [-3.5, -3], "center": [-3.5, -4]},
        ]
    },
    "mall_floor": {
        "start": (0, 0),
        "obstacles": [],
        "rooms": [
            {"name": "main_corridor", "polygon": [[-7, -1], [7, -1], [7, 1], [-7, 1]], "entry_point": [0, -1], "center": [0, 0]},
            {"name": "shop_a", "polygon": [[-7, 1], [-3, 1], [-3, 5], [-7, 5]], "entry_point": [-5, 1], "center": [-5, 3]},
            {"name": "shop_b", "polygon": [[-3, 1], [1, 1], [1, 5], [-3, 5]], "entry_point": [-1, 1], "center": [-1, 3]},
            {"name": "shop_c", "polygon": [[1, 1], [5, 1], [5, 5], [1, 5]], "entry_point": [3, 1], "center": [3, 3]},
            {"name": "shop_d", "polygon": [[5, 1], [7, 1], [7, 5], [5, 5]], "entry_point": [6, 1], "center": [6, 3]},
            {"name": "shop_e", "polygon": [[-7, -5], [-3, -5], [-3, -1], [-7, -1]], "entry_point": [-5, -1], "center": [-5, -3]},
            {"name": "shop_f", "polygon": [[-3, -5], [1, -5], [1, -1], [-3, -1]], "entry_point": [-1, -1], "center": [-1, -3]},
            {"name": "food_court", "polygon": [[1, -5], [7, -5], [7, -1], [1, -1]], "entry_point": [4, -1], "center": [4, -3]},
        ]
    },

}

def load_scenario(name="villa"):
    scenario = SCENARIOS.get(name, SCENARIOS["villa"]).copy()
    # 向后兼容：确保返回的字典包含 rooms 键
    if "rooms" not in scenario:
        scenario["rooms"] = []
    return scenario


if __name__ == "__main__":
    print(load_scenario("villa"))