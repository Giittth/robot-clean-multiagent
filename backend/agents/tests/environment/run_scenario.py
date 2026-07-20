from backend.agents.simulation.scenario_loader import load_scenario

scenario = load_scenario("standard")
print(scenario["start"])
print(len(scenario["obstacles"]))
print(scenario["rooms"])  # 应显示两个房间的定义