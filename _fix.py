import re
with open("D:\\Users\\ye0106\\PycharmProjects\\Agent_001\\backend\\agents\\implementations\\supervisor_agent.py", encoding="utf-8") as f:
    content = f.read()

old_total = "len(self.current_context.task_status) if self.current_context else 0"
new_total = "sum(1 for s in self.current_context.task_status.values() if s != TaskState.SKIPPED) if self.current_context else 0"

if old_total in content:
    content = content.replace(old_total, new_total, 1)
    print("Fix applied: graph_total counts non-SKIPPED")
else:
    print("NOT APPLIED")
    idx = content.find("graph_total")
    if idx > 0:
        print(repr(content[idx:idx+120]))

with open("D:\\Users\\ye0106\\PycharmProjects\\Agent_001\\backend\\agents\\implementations\\supervisor_agent.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
