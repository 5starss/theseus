
import json
import uuid
import os

# 원본 파일 경로와 새로운 파일 경로 정의
original_file_path = "temp/plan.json"
new_file_path = "temp/plan_refactored.json"

# 디렉터리가 없는 경우 생성
os.makedirs("temp", exist_ok=True)

# 원본 JSON 파일 읽기
try:
    with open(original_file_path, "r", encoding="utf-8") as f:
        plan = json.load(f)
except FileNotFoundError:
    print(f"Error: The file {original_file_path} was not found.")
    exit(1)
except json.JSONDecodeError:
    print(f"Error: The file {original_file_path} is not a valid JSON file.")
    exit(1)


# 새로운 태스크 리스트 생성
new_tasks = []

# 각 단계를 메인 태스크로 변환
for step in plan.get("steps", []):
    main_task_id = str(uuid.uuid4())
    
    new_tasks.append({
        "id": main_task_id,
        "parent_id": None,
        "title": step.get("title", "No Title"),
        "description": step.get("description", ""),
        "status": "pending"
    })

    # 각 하위 태스크를 서브 태스크로 변환
    for sub_task_description in step.get("sub_tasks", []):
        sub_task_id = str(uuid.uuid4())
        new_tasks.append({
            "id": sub_task_id,
            "parent_id": main_task_id,
            "title": sub_task_description,
            "description": sub_task_description,
            "status": "pending"
        })

# 최종 결과 데이터 구성
output_data = {
    "goal": plan.get("goal"),
    "tasks": new_tasks
}

# 새로운 구조의 JSON 파일을 저장
with open(new_file_path, "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print(f"JSON 구조 변경 완료. 새로운 파일이 다음 경로에 저장되었습니다: {new_file_path}")
